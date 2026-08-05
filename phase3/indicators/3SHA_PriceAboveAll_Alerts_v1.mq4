//+------------------------------------------------------------------+
//|                                 3SHA_PriceAboveAll_Alerts_v1.mq4 |
//|   MT4 port of phase1/indicators/3SHA_PriceAboveAll_Alerts_v1.pine |
//+------------------------------------------------------------------+
//
//  WHAT THIS IS
//    A line-for-line port of the Pine v6 companion indicator. It rebuilds
//    the three SHA layers, runs the same hypothetical trade state machine
//    (entry -> stop -> break-even -> trail -> exits), and raises MT4 alerts
//    on the same events the Pine alertcondition() calls cover.
//
//  SIGNAL TIMING
//    Everything is CLOSE-BASED, exactly as the Pine note demands ("Once Per
//    Bar Close"). The state machine only ever processes bars that have
//    already closed. Bar 0 is drawn for display but never generates a
//    signal, so nothing can appear and then vanish.
//
//  DELIBERATE DEVIATIONS FROM THE PINE (all forced by MT4, none silent)
//
//    1. HTF ALIGNMENT. Pine's request.security(..., lookahead_off) returns
//       the last CLOSED higher-timeframe bar on history, but the DEVELOPING
//       bar in real time. That is the well-known history/realtime split that
//       makes TradingView repaint on reload. This port defaults to the
//       closed-bar reading, so MT4 matches what the Pine BACKTEST showed and
//       never repaints. Set HTF_UseDevelopingBar = true to match what
//       TradingView shows you live instead. Default false.
//
//    2. GAP FILTER OFF-BY-ONE (inherited, not introduced). Because
//       lookahead_off returns the last closed daily bar, the Pine's day_open
//       / day_pclose are YESTERDAY's open and the day-before's close - so the
//       gap being tested on a new day is the PREVIOUS day's gap, not today's.
//       This port reproduces that faithfully. If that was not the intent it
//       is a bug in the Pine and needs fixing THERE first, so both stay in
//       step. Not changed here unilaterally.
//
//    3. NO TRANSPARENCY. MT4 has no alpha channel, so the Pine opacity
//       settings (0 / 25 / 50) cannot be reproduced. The three layers are
//       instead separated by BAR WIDTH: HTF2 widest and drawn first, base
//       narrowest and drawn last, so all three stay readable.
//
//    4. NO WICKS. MT4 allows only 8 DRAWN indicator buffers. Three candle
//       bodies take six, the stop line a seventh. Wicks for three layers
//       would need six more. Bodies only. The Pine default is show_wicks =
//       false, so the default view is unchanged.
//
//    5. RAW CANDLE SOURCE. The Pine uses ticker.standard() to protect the
//       calculation from Renko / Heikin-Ashi chart types. MT4 charts are
//       always standard OHLC, so Open/High/Low/Close are used directly.
//       Same result, no wrapper needed.
//
//    6. CLOCK. The Pine daily cutoff uses exchange time and follows DST on
//       its own. MT4 has no exchange calendar, so the cutoff here is BROKER
//       SERVER time. Check your broker's server offset before setting it.
//
//    7. EMA SEEDING. Pine's ta.ema seeds from an SMA of the first len bars.
//       This port seeds from the first raw value. With len 4 and 8 the two
//       converge to identical values within ~30 bars; WarmupBars (default 100)
//       blocks signals until well past that point.
//
//    8. STOP LINE. Pine plots plot.style_stepline. MT4 has no stepline, so
//       the stop renders as a plain line and will slope between steps.
//
//  FOREX NOTES
//    DISTANCE UNITS. The Pine expresses every distance as a percentage of
//    price, which is the right normaliser for equities but not for FX: 0.10%
//    is 6.5 pips on AUDUSD at 0.6500 and 15 pips on USDJPY at 150.00, while
//    their daily ranges are nowhere near 2.3x apart. Set DistanceUnit = Pips
//    to use pip-denominated stop buffer, min stop, break-even offset and
//    trail buffer instead. Percent is the default so Pine parity is kept.
//    A pip is auto-sized: 10 x Point on 5- and 3-digit brokers, Point
//    otherwise, so 4-digit, 5-digit and JPY pairs all behave the same.
//
//    BID-ONLY CHARTS. MT4 draws BID. A short's stop executes on the ASK, so
//    a short can be stopped out when ask crosses the level even though the
//    bid high never touched it. Set ShortsPaySpread = true to test short
//    stops against bid + spread. Default false, again for Pine parity.
//    Entry fills and the R calculation stay bid-based, as in the Pine -
//    only the stop-hit test is spread-aware. Note the live broker spread is
//    applied to historical bars too, so for a repeatable historical
//    comparison set SpreadPipsOverride to a fixed value.
//
//    THE GAP FILTER IS NEARLY INERT ON SPOT FX. It is 24/5, so the only real
//    gap is the Sunday open. Worse, the daily boundary is your broker's
//    server midnight, not any market close, and many brokers post a short
//    Sunday D1 bar that both fakes a new day and distorts the gap maths.
//    Treat GapThresh as a weekend filter or leave it at 0.
//
//    THE DAILY CUTOFF IS SERVER TIME AND DOES NOT FOLLOW DST. Most FX brokers
//    shift their server offset with US daylight saving, so a fixed cutoff
//    hour drifts an hour against London and New York twice a year. There is
//    no exchange close on spot FX to anchor it to. Check the Experts log
//    line this indicator prints on attach for the symbol's actual settings.
//
//  BUFFER MAP
//    0/1 HTF2 body   2/3 HTF1 body   4/5 base body
//    6   active stop line
//    7   position state (Data Window only: 1 long, -1 short, 0 flat)
//    8-25 calculation buffers, not drawn
//
//+------------------------------------------------------------------+
#property copyright "3SHA"
#property link      "https://github.com/mesan4net-blip/algo-trading-system"
#property version   "1.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 8

#define NA        DBL_MAX
#define OBJPREFIX "3SHAPA_"

bool IsNA(double v) { return(v==NA || v==EMPTY_VALUE); }

//====================================================================
// ENUMS
//====================================================================
enum EN_PA_LAYERS
  {
   PA_ALL3=0,      // All three
   PA_H1H2,        // HTF1 + HTF2
   PA_B_H1,        // Base + HTF1
   PA_B_H2,        // Base + HTF2
   PA_H2ONLY,      // HTF2 only
   PA_H1ONLY,      // HTF1 only
   PA_BASEONLY,    // Base only
   PA_ANY2         // Any two
  };

enum EN_CONFIRM
  {
   CF_1BAR=0,      // Confirmed (1-bar)
   CF_IMMEDIATE    // Immediate
  };

enum EN_BASIS
  {
   BS_BODY=0,      // Body (open/close)
   BS_WICK         // Wick (high/low)
  };

enum EN_SL_MODE
  {
   SL_TRIGGER=0,   // Trigger Candle
   SL_SWING,       // Swing (Prev N Bars)
   SL_BASE,        // Base SHA Body
   SL_HTF1,        // HTF1 SHA Body
   SL_HTF2,        // HTF2 SHA Body
   SL_LBAR_NEAR,   // Last Bar Beyond Nearest SHA
   SL_LBAR_FAR,    // Last Bar Beyond Furthest SHA
   SL_LSHA_NEAR,   // Last SHA Bar Beyond Nearest SHA
   SL_LSHA_FAR,    // Last SHA Bar Beyond Furthest SHA
   SL_EL_NEAR,     // Closest Eligible SHA
   SL_EL_MID,      // Middle Eligible SHA
   SL_EL_FAR       // Furthest Eligible SHA
  };

enum EN_TRAIL_MODE
  {
   TR_SWING=0,     // Swing (Prev N Bars)
   TR_BASE,        // Base SHA Body
   TR_HTF1,        // HTF1 SHA Body
   TR_HTF2,        // HTF2 SHA Body
   TR_EL_NEAR,     // Closest Eligible SHA
   TR_EL_MID,      // Middle Eligible SHA
   TR_EL_FAR       // Furthest Eligible SHA
  };

enum EN_LAYER
  {
   LY_BASE=0,      // Base
   LY_HTF1,        // HTF1
   LY_HTF2         // HTF2
  };

enum EN_FLIP
  {
   FL_BASE=0,      // Base Flips
   FL_HTF1,        // HTF1 Flips
   FL_HTF2,        // HTF2 Flips
   FL_ANY,         // Any Layer Flips
   FL_ALL          // All Layers Flip
  };

enum EN_REENTRY
  {
   RE_PATTERN=0,   // Two-candle pattern
   RE_CLOSEREF     // Close beyond reference
  };

enum EN_LBLSIZE
  {
   LS_TINY=6,      // Tiny
   LS_SMALL=8,     // Small
   LS_NORMAL=10,   // Normal
   LS_LARGE=13,    // Large
   LS_HUGE=16      // Huge
  };

enum EN_DIST_UNIT
  {
   DU_PERCENT=0,   // Percent of price
   DU_PIPS         // Pips
  };

//====================================================================
// INPUTS
//====================================================================
input string  s01 = "=== BASE LAYER (chart TF) ===";        // .
input int     BaseLen1        = 4;                           // Base Stage-1 EMA
input int     BaseLen2        = 8;                           // Base Stage-2 EMA
input bool    BaseShow        = true;                        // Show Base SHA Candles
input color   BaseBull        = C'41,98,255';                // Base Bull Color
input color   BaseBear        = C'255,152,0';                // Base Bear Color
input int     BaseWidth       = 1;                           // Base Bar Width

input string  s02 = "=== HTF1 - MID LAYER ===";              // .
input ENUM_TIMEFRAMES Htf1TF  = PERIOD_H1;                   // HTF1 Timeframe
input int     Htf1Len1        = 4;                           // HTF1 Stage-1 EMA
input int     Htf1Len2        = 8;                           // HTF1 Stage-2 EMA
input bool    Htf1Show        = true;                        // Show HTF1 SHA Candles
input color   Htf1Bull        = C'41,98,255';                // HTF1 Bull Color
input color   Htf1Bear        = C'242,54,69';                // HTF1 Bear Color
input int     Htf1Width       = 3;                           // HTF1 Bar Width

input string  s03 = "=== HTF2 - SLOW LAYER ===";             // .
input ENUM_TIMEFRAMES Htf2TF  = PERIOD_H4;                   // HTF2 Timeframe
input int     Htf2Len1        = 4;                           // HTF2 Stage-1 EMA
input int     Htf2Len2        = 8;                           // HTF2 Stage-2 EMA
input bool    Htf2Show        = true;                        // Show HTF2 SHA Candles
input color   Htf2Bull        = C'41,98,255';                // HTF2 Bull Color
input color   Htf2Bear        = C'242,54,69';                // HTF2 Bear Color
input int     Htf2Width       = 5;                           // HTF2 Bar Width

input string  s04 = "=== ENTRY: PRICE ABOVE ALL ===";        // .
input EN_PA_LAYERS PaLayers   = PA_ALL3;                     // Price Must Clear
input EN_CONFIRM   ConfirmMode= CF_1BAR;                     // Confirmation Mode
input bool    AllowLongs      = true;                        // Allow Longs
input bool    AllowShorts     = true;                        // Allow Shorts
input bool    EntryNeedsDir   = true;                        // Entry Candle Must Match Direction
input bool    UseReentry      = false;                       // Re-Enter After Exit
input bool    ReentryNeedsBase= true;                        //   Setup Must Still Hold
input EN_REENTRY ReentryStyle = RE_PATTERN;                  //   Re-Entry Style
input EN_LAYER   ReentryLayer = LY_BASE;                     //   Re-Entry Trigger Layer
input double  GapThresh       = 0.0;                         // Skip Gap Entries Above (%)

input string  s05 = "=== INITIAL STOP ===";                  // .
input EN_SL_MODE SlMode       = SL_SWING;                    // Stop Anchor
input EN_BASIS   SlPriceBasis = BS_BODY;                     // Anchor Uses
input int     SlLookback      = 10;                          // Swing Lookback (bars)
input double  SlBufferPct     = 0.10;                        // Stop Buffer (%)
input double  MinStopPct      = 0.00;                        // Min Stop Distance (%)
input bool    UseHardStop     = false;                       // Hard Stop (intra-bar)

input string  s06 = "=== TRADE MANAGEMENT ===";              // .
input bool    UseBE           = true;                        // Move Stop To Break-Even
input double  BeTriggerR      = 1.0;                         //   Break-Even Trigger (R)
input double  BeOffsetPct     = 0.00;                        //   Break-Even Offset (%)
input bool    UseTrail        = true;                        // Trailing Stop
input EN_TRAIL_MODE TrailMode = TR_SWING;                    //   Trail Anchor
input EN_BASIS TrailPriceBasis= BS_BODY;                     //   Trail Uses
input double  TrailStartR     = 1.0;                         //   Trail Activates At (R)
input int     TrailLookback   = 6;                           //   Trail Lookback (bars)
input double  TrailBufferPct  = 0.10;                        //   Trail Buffer (%)
input bool    ReverseOnStop   = false;                       // Reverse On Stop
input int     AlignConfirmBars= 1;                           //   Flip Must Hold (bars)
input bool    UseShaBreak     = false;                       // Exit: Price Back Through SHA
input EN_LAYER ShaBreakLayer  = LY_HTF1;                     //   Which Layer
input bool    UseTarget       = false;                       // Exit: Profit Target
input double  TargetR         = 3.0;                         //   Target (R)
input bool    UseGiveback     = false;                       // Exit: Give-Back
input double  GivebackPct     = 40.0;                        //   Give-Back (% of peak)
input double  GivebackMinR    = 1.0;                         //   Only After (R)
input bool    UseTimeStop     = false;                       // Exit: Time Stop
input int     TimeStopBars    = 30;                          //   After (bars)
input double  TimeStopMinR    = 0.5;                         //   Unless Ahead By (R)
input bool    UseCrossExit    = false;                       // Exit: Chart SHA Crosses Mid SHA
input bool    UseAlignExit    = false;                       // Exit: Layer Flips Direction
input EN_FLIP AlignBreakLevel = FL_HTF1;                     //   Flip Trigger

input string  s07 = "=== DATE / SESSION FILTER ===";         // .
input bool    UseDate         = false;                       // Enable Date Range
input datetime DateStart      = D'2025.01.01 00:00';         // Start
input datetime DateEnd        = D'2026.12.31 23:59';         // End
input bool    UseEod          = false;                       // Daily Cutoff
input int     EodHour         = 15;                          //   Cutoff Hour (SERVER time, 0-23)
input int     EodMinute       = 55;                          //   Cutoff Minute
input bool    EodBlockEntries = true;                        //   Block New Entries After Cutoff

input string  s08 = "=== ALERTS ===";                        // .
input bool    AlEntry         = true;                        // Entry alerts
input bool    AlExit          = true;                        // Exit-signal alerts
input bool    AlStop          = true;                        // Stop-hit alerts
input bool    AlSignalOnly    = false;                       // Signal-only mode (ignore position state)
input bool    AlertPopup      = true;                        // Popup alert
input bool    AlertSound      = true;                        // Play sound
input string  AlertSoundFile  = "alert.wav";                 //   Sound file
input bool    AlertPush       = false;                       // Push notification
input bool    AlertEmail      = false;                       // Email

input string  s09 = "=== DISPLAY ===";                       // .
input bool    ShowMarks       = true;                        // Show entry/exit markers
input bool    ShowPriceLabels = true;                        // Show entry/exit price labels
input double  LabelOffsetPct  = 0.30;                        //   Label distance (%)
input EN_LBLSIZE LabelSize    = LS_SMALL;                    //   Label Size
input bool    ShowStop        = true;                        // Show active stop line
input bool    ShowPanel       = true;                        // Show status panel
input color   ColBull         = C'41,98,255';                // Bull / Long
input color   ColBear         = C'242,54,69';                // Bear / Short
input color   ColStop         = C'255,152,0';                // Stop
input color   ColExit         = C'255,152,0';                // Other Exit

input string  s10 = "=== ENGINE ===";                        // .
input bool    HTF_UseDevelopingBar = false;                  // HTF: use developing bar (matches TV live)
input int     MaxBars         = 5000;                        // Max chart bars to process (0 = all)
input int     WarmupBars      = 100;                         // Warmup bars before signals allowed
input int     MaxMarkerBars   = 1500;                        // Only draw markers within N bars

input string  s11 = "=== FOREX / INSTRUMENT ===";            // .
input EN_DIST_UNIT DistanceUnit = DU_PERCENT;                // Distance Units
input double  SlBufferPips    = 10.0;                        //   Stop Buffer (pips)
input double  MinStopPips     = 0.0;                         //   Min Stop Distance (pips)
input double  BeOffsetPips    = 0.0;                         //   Break-Even Offset (pips)
input double  TrailBufferPips = 10.0;                        //   Trail Buffer (pips)
input bool    ShortsPaySpread = false;                       // Short stops tested on ASK
input double  SpreadPipsOverride = 0.0;                      //   Fixed spread (pips, 0 = live)

//====================================================================
// BUFFERS
//====================================================================
double b_h2A[], b_h2B[];      // 0,1  HTF2 body
double b_h1A[], b_h1B[];      // 2,3  HTF1 body
double b_bsA[], b_bsB[];      // 4,5  base body
double b_stop[];              // 6    active stop
double b_state[];             // 7    position state

double c_bO1[], c_bH1[], c_bL1[], c_bC1[];        //  8-11
double c_bHaO[], c_bHaC[];                        // 12,13
double c_bO2[], c_bH2[], c_bL2[], c_bC2[];        // 14-17
double c_m1O[], c_m1H[], c_m1L[], c_m1C[];        // 18-21
double c_m2O[], c_m2H[], c_m2L[], c_m2C[];        // 22-25

// higher-timeframe SHA series, indexed by that timeframe's own shift
double h1O[], h1H[], h1L[], h1C[];
double h2O[], h2H[], h2L[], h2C[];
int    h1Count = 0, h2Count = 0;
datetime h1Stamp = 0, h2Stamp = 0;

//====================================================================
// STATE MACHINE GLOBALS
//====================================================================
string   g_posDir      = "flat";
double   g_entryPrice  = NA;
double   g_stopLevel   = NA;
double   g_riskUnit    = NA;
bool     g_beMoved     = false;
int      g_badBars     = 0;
double   g_peakR       = 0.0;
int      g_entryAbs    = -1;
double   g_rearmHigh   = NA;
double   g_rearmLow    = NA;
bool     g_eligB=false, g_elig1=false, g_elig2=false;
bool     g_armB=false,  g_arm1=false,  g_arm2=false;
double   g_trigHigh    = NA;
double   g_trigLow     = NA;
double   g_lblEntryPx  = NA;

// "last bar beyond" trackers
double   g_xlPxH1=NA, g_xlPxH2=NA, g_xlHaH1=NA, g_xlHaH2=NA;
double   g_xhPxH1=NA, g_xhPxH2=NA, g_xhHaH1=NA, g_xhHaH2=NA;

// one- and two-bar history of the alignment flags
bool     g_allBull1=false, g_allBull2=false;
bool     g_allBear1=false, g_allBear2=false;
// previous-bar values for the crossover test
double   g_prevBaseC=NA, g_prevH1C=NA;

int      g_absBar      = 0;
datetime g_lastProcTime= 0;
bool     g_firstPass   = true;

//====================================================================
// SMALL HELPERS
//====================================================================
bool OK(double v) { return(v!=EMPTY_VALUE && v!=NA && v!=0.0); }

//  One pip. 10 x Point on 5-digit and 3-digit (JPY) brokers, Point otherwise,
//  so 4-digit, 5-digit and JPY pairs all take the same pip input.
double PipSize()
  {
   return((Digits==3 || Digits==5) ? Point*10.0 : Point);
  }

//  Distance in price terms, from whichever unit the user chose.
double DistRaw(double pctVal,double pipVal,double px)
  {
   if(DistanceUnit==DU_PIPS) return(pipVal*PipSize());
   return(px*pctVal/100.0);
  }

//  MT4 charts are BID. A short exits on the ASK, so the stop-hit test needs
//  the spread added back. Override beats live spread for repeatable history.
double SpreadRaw()
  {
   if(!ShortsPaySpread) return(0.0);
   if(SpreadPipsOverride>0.0) return(SpreadPipsOverride*PipSize());
   return(MarketInfo(Symbol(),MODE_SPREAD)*Point);
  }

double LowestWickAt(int start,int count)
  {
   int k = iLowest(Symbol(),0,MODE_LOW,count,start);
   if(k<0) return(NA);
   return(Low[k]);
  }
double HighestWickAt(int start,int count)
  {
   int k = iHighest(Symbol(),0,MODE_HIGH,count,start);
   if(k<0) return(NA);
   return(High[k]);
  }
double LowestBodyAt(int start,int count)
  {
   double v = NA;
   for(int k=start; k<start+count && k<Bars; k++)
     {
      double x = MathMin(Open[k],Close[k]);
      if(IsNA(v) || x<v) v = x;
     }
   return(v);
  }
double HighestBodyAt(int start,int count)
  {
   double v = NA;
   for(int k=start; k<start+count && k<Bars; k++)
     {
      double x = MathMax(Open[k],Close[k]);
      if(IsNA(v) || x>v) v = x;
     }
   return(v);
  }

//  Mirrors Pine f_rank: [closest, middle, furthest] from the reference by
//  absolute distance. Two eligible -> middle resolves to furthest. One -> all
//  three resolve to it. None -> all NA and the caller falls back to Swing.
void FRank(bool e0,double l0,bool e1,double l1,bool e2,double l2,double ref,
           double &vNear,double &vMid,double &vFar)
  {
   double lv[3], ds[3];
   int n = 0;
   if(e0 && OK(l0)) { lv[n]=l0; n++; }
   if(e1 && OK(l1)) { lv[n]=l1; n++; }
   if(e2 && OK(l2)) { lv[n]=l2; n++; }
   vNear = NA; vMid = NA; vFar = NA;
   if(n==0) return;
   for(int k=0;k<n;k++) ds[k] = MathAbs(ref-lv[k]);
   for(int a=0;a<n-1;a++)
      for(int b=a+1;b<n;b++)
         if(ds[b]<ds[a])
           {
            double t=ds[a]; ds[a]=ds[b]; ds[b]=t;
            t=lv[a]; lv[a]=lv[b]; lv[b]=t;
           }
   vNear = lv[0];
   vFar  = lv[n-1];
   vMid  = (n>=3) ? lv[1] : vFar;
  }

void FireAlert(string msg)
  {
   if(AlertPopup) Alert(msg); else Print(msg);
   if(AlertSound) PlaySound(AlertSoundFile);
   if(AlertPush)  SendNotification(msg);
   if(AlertEmail) SendMail("3SHA-PA", msg);
  }

void MakeArrow(string name,datetime t,double price,int code,color c,int width)
  {
   if(ObjectFind(name)>=0) return;
   ObjectCreate(name,OBJ_ARROW,0,t,price);
   ObjectSet(name,OBJPROP_ARROWCODE,code);
   ObjectSet(name,OBJPROP_COLOR,c);
   ObjectSet(name,OBJPROP_WIDTH,width);
   ObjectSet(name,OBJPROP_BACK,false);
  }

void MakeText(string name,datetime t,double price,string txt,color c,int fsize)
  {
   if(ObjectFind(name)>=0) ObjectDelete(name);
   ObjectCreate(name,OBJ_TEXT,0,t,price);
   ObjectSetText(name,txt,fsize,"Arial",c);
   ObjectSet(name,OBJPROP_BACK,false);
  }

void ClearObjects()
  {
   for(int k=ObjectsTotal()-1;k>=0;k--)
     {
      string nm = ObjectName(k);
      if(StringFind(nm,OBJPREFIX,0)==0) ObjectDelete(nm);
     }
  }

//====================================================================
// SHA SERIES FOR A GIVEN TIMEFRAME  (two-pass EMA -> HA -> EMA)
//   Mirrors Pine f_sha exactly. Seeded from the first raw value rather
//   than an SMA; see deviation 7 in the header.
//====================================================================
bool BuildLayerSHA(ENUM_TIMEFRAMES tf,int len1,int len2,
                   double &ao[],double &ah[],double &al[],double &ac[],int &outCount)
  {
   int n = iBars(Symbol(),tf);
   if(n < 60) { outCount = 0; return(false); }

   ArraySetAsSeries(ao,false); ArraySetAsSeries(ah,false);
   ArraySetAsSeries(al,false); ArraySetAsSeries(ac,false);
   ArrayResize(ao,n); ArrayResize(ah,n); ArrayResize(al,n); ArrayResize(ac,n);
   ArraySetAsSeries(ao,true); ArraySetAsSeries(ah,true);
   ArraySetAsSeries(al,true); ArraySetAsSeries(ac,true);

   double a1 = 2.0/(len1+1.0);
   double a2 = 2.0/(len2+1.0);
   double po1=0,ph1=0,pl1=0,pc1=0,phaO=0,phaC=0,po2=0,ph2=0,pl2=0,pc2=0;

   for(int k=n-1;k>=0;k--)
     {
      double O=iOpen(Symbol(),tf,k), H=iHigh(Symbol(),tf,k);
      double L=iLow(Symbol(),tf,k),  C=iClose(Symbol(),tf,k);
      double o1,h1,l1,c1,haC,haO,haH,haL,o2,h2,l2,c2;

      if(k==n-1) { o1=O; h1=H; l1=L; c1=C; }
      else
        {
         o1 = a1*O + (1.0-a1)*po1;
         h1 = a1*H + (1.0-a1)*ph1;
         l1 = a1*L + (1.0-a1)*pl1;
         c1 = a1*C + (1.0-a1)*pc1;
        }

      haC = (o1+h1+l1+c1)/4.0;
      haO = (k==n-1) ? (o1+c1)/2.0 : (phaO+phaC)/2.0;
      haH = MathMax(h1,MathMax(haO,haC));
      haL = MathMin(l1,MathMin(haO,haC));

      if(k==n-1) { o2=haO; h2=haH; l2=haL; c2=haC; }
      else
        {
         o2 = a2*haO + (1.0-a2)*po2;
         h2 = a2*haH + (1.0-a2)*ph2;
         l2 = a2*haL + (1.0-a2)*pl2;
         c2 = a2*haC + (1.0-a2)*pc2;
        }

      ao[k]=o2; ah[k]=h2; al[k]=l2; ac[k]=c2;
      po1=o1; ph1=h1; pl1=l1; pc1=c1;
      phaO=haO; phaC=haC;
      po2=o2; ph2=h2; pl2=l2; pc2=c2;
     }
   outCount = n;
   return(true);
  }

//  Chart bar i -> the higher-timeframe bar Pine would have been reading.
//  Default is the last CLOSED bar (non-repainting, matches Pine history).
bool MapHTF(int i,ENUM_TIMEFRAMES tf,double &ao[],double &ah[],double &al[],double &ac[],
            int cnt,double &oO,double &oH,double &oL,double &oC)
  {
   if(cnt<=0) return(false);
   int sh = iBarShift(Symbol(),tf,Time[i],false);
   if(sh<0) return(false);
   int use = HTF_UseDevelopingBar ? sh : sh+1;
   if(use<0 || use>=cnt) return(false);
   oO=ao[use]; oH=ah[use]; oL=al[use]; oC=ac[use];
   return(true);
  }

//====================================================================
// RESET
//====================================================================
void ResetState()
  {
   g_posDir="flat"; g_entryPrice=NA; g_stopLevel=NA; g_riskUnit=NA;
   g_beMoved=false; g_badBars=0; g_peakR=0.0; g_entryAbs=-1;
   g_rearmHigh=NA; g_rearmLow=NA;
   g_eligB=false; g_elig1=false; g_elig2=false;
   g_armB=false;  g_arm1=false;  g_arm2=false;
   g_trigHigh=NA; g_trigLow=NA; g_lblEntryPx=NA;
   g_xlPxH1=NA; g_xlPxH2=NA; g_xlHaH1=NA; g_xlHaH2=NA;
   g_xhPxH1=NA; g_xhPxH2=NA; g_xhHaH1=NA; g_xhHaH2=NA;
   g_allBull1=false; g_allBull2=false; g_allBear1=false; g_allBear2=false;
   g_prevBaseC=NA; g_prevH1C=NA;
   g_absBar=0; g_lastProcTime=0; g_firstPass=true;
  }

//====================================================================
// INIT
//====================================================================
int OnInit()
  {
   IndicatorBuffers(26);

   SetIndexBuffer(0,b_h2A);  SetIndexBuffer(1,b_h2B);
   SetIndexBuffer(2,b_h1A);  SetIndexBuffer(3,b_h1B);
   SetIndexBuffer(4,b_bsA);  SetIndexBuffer(5,b_bsB);
   SetIndexBuffer(6,b_stop); SetIndexBuffer(7,b_state);

   SetIndexBuffer(8, c_bO1);  SetIndexBuffer(9, c_bH1);
   SetIndexBuffer(10,c_bL1);  SetIndexBuffer(11,c_bC1);
   SetIndexBuffer(12,c_bHaO); SetIndexBuffer(13,c_bHaC);
   SetIndexBuffer(14,c_bO2);  SetIndexBuffer(15,c_bH2);
   SetIndexBuffer(16,c_bL2);  SetIndexBuffer(17,c_bC2);
   SetIndexBuffer(18,c_m1O);  SetIndexBuffer(19,c_m1H);
   SetIndexBuffer(20,c_m1L);  SetIndexBuffer(21,c_m1C);
   SetIndexBuffer(22,c_m2O);  SetIndexBuffer(23,c_m2H);
   SetIndexBuffer(24,c_m2L);  SetIndexBuffer(25,c_m2C);

   //  Histogram pairs. MT4 draws a bar between two adjacent DRAW_HISTOGRAM
   //  buffers and colours it from whichever buffer holds the LARGER value.
   //  Buffer A holds the SHA open, buffer B the SHA close, so B's colour
   //  shows on an up bar and A's on a down bar. Hence A = bear, B = bull.
   SetIndexStyle(0,Htf2Show?DRAW_HISTOGRAM:DRAW_NONE,STYLE_SOLID,Htf2Width,Htf2Bear);
   SetIndexStyle(1,Htf2Show?DRAW_HISTOGRAM:DRAW_NONE,STYLE_SOLID,Htf2Width,Htf2Bull);
   SetIndexStyle(2,Htf1Show?DRAW_HISTOGRAM:DRAW_NONE,STYLE_SOLID,Htf1Width,Htf1Bear);
   SetIndexStyle(3,Htf1Show?DRAW_HISTOGRAM:DRAW_NONE,STYLE_SOLID,Htf1Width,Htf1Bull);
   SetIndexStyle(4,BaseShow?DRAW_HISTOGRAM:DRAW_NONE,STYLE_SOLID,BaseWidth,BaseBear);
   SetIndexStyle(5,BaseShow?DRAW_HISTOGRAM:DRAW_NONE,STYLE_SOLID,BaseWidth,BaseBull);
   SetIndexStyle(6,ShowStop?DRAW_LINE:DRAW_NONE,STYLE_SOLID,1,ColStop);
   SetIndexStyle(7,DRAW_NONE);

   for(int k=0;k<26;k++) SetIndexEmptyValue(k,EMPTY_VALUE);

   SetIndexLabel(0,"HTF2 SHA open");  SetIndexLabel(1,"HTF2 SHA close");
   SetIndexLabel(2,"HTF1 SHA open");  SetIndexLabel(3,"HTF1 SHA close");
   SetIndexLabel(4,"Base SHA open");  SetIndexLabel(5,"Base SHA close");
   SetIndexLabel(6,"Active stop");    SetIndexLabel(7,"Position (1/-1/0)");
   for(int m=8;m<26;m++) SetIndexLabel(m,NULL);

   ArraySetAsSeries(h1O,true); ArraySetAsSeries(h1H,true);
   ArraySetAsSeries(h1L,true); ArraySetAsSeries(h1C,true);
   ArraySetAsSeries(h2O,true); ArraySetAsSeries(h2H,true);
   ArraySetAsSeries(h2L,true); ArraySetAsSeries(h2C,true);

   IndicatorShortName("3SHA-PA Alerts");
   PrintFormat("3SHA-PA attached: %s  Digits=%d  Point=%s  Pip=%s  spread=%d pts  server=%s",
               Symbol(),Digits,DoubleToString(Point,8),DoubleToString(PipSize(),8),
               (int)MarketInfo(Symbol(),MODE_SPREAD),TimeToString(TimeCurrent(),TIME_DATE|TIME_SECONDS));
   ClearObjects();
   ResetState();
   h1Stamp=0; h2Stamp=0; h1Count=0; h2Count=0;
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ClearObjects();
   Comment("");
  }

//====================================================================
// STATUS PANEL
//====================================================================
void DrawPanel(bool baseBull,bool htf1Bull,bool htf2Bull)
  {
   if(!ShowPanel) { Comment(""); return; }
   string dir = (g_posDir=="flat") ? "---" : g_posDir;
   StringToUpper(dir);
   string txt = "3SHA-PA   " + dir + "\n";
   txt += "Base : " + (baseBull?"bull":"bear") + "\n";
   txt += "HTF1 : " + (htf1Bull?"bull":"bear") + "\n";
   txt += "HTF2 : " + (htf2Bull?"bull":"bear") + "\n";
   txt += "Stop : " + ((g_posDir=="flat"||IsNA(g_stopLevel)) ? "---"
                       : DoubleToString(g_stopLevel,Digits)) + "\n";
   Comment(txt);
  }

//====================================================================
// STATE MACHINE — one closed bar
//   Order of operations mirrors the Pine top to bottom: alignment, then
//   eligibility/arming, then ranking, then management of the open trade,
//   then re-entry references, then entries.
//====================================================================
void ProcessBar(int i,bool live)
  {
   g_absBar++;

   double rawO=Open[i], rawH=High[i], rawL=Low[i], rawC=Close[i];
   double bO=c_bO2[i], bH=c_bH2[i], bL=c_bL2[i], bC=c_bC2[i];
   double m1O=c_m1O[i], m1H=c_m1H[i], m1L=c_m1L[i], m1C=c_m1C[i];
   double m2O=c_m2O[i], m2H=c_m2H[i], m2L=c_m2L[i], m2C=c_m2C[i];

   bool baseReady = OK(bO) && OK(bC);
   bool htf1Ready = OK(m1O) && OK(m1C);
   bool htf2Ready = OK(m2O) && OK(m2C);
   bool allReady  = baseReady && htf1Ready && htf2Ready && (g_absBar > WarmupBars);

   if(!allReady)
     {
      g_allBull2=g_allBull1; g_allBull1=false;
      g_allBear2=g_allBear1; g_allBear1=false;
      b_stop[i]=EMPTY_VALUE; b_state[i]=0;
      return;
     }

   bool baseBullBar = (bC>=bO);
   bool htf1BullBar = (m1C>=m1O);
   bool htf2BullBar = (m2C>=m2O);

   double shaBot0=MathMin(bO,bC),   shaTop0=MathMax(bO,bC);
   double shaBot1=MathMin(m1O,m1C), shaTop1=MathMax(m1O,m1C);
   double shaBot2=MathMin(m2O,m2C), shaTop2=MathMax(m2O,m2C);

   bool slBody = (SlPriceBasis==BS_BODY);

   //--- alignment: where price SITS, not which way each layer points
   double paBTop = slBody?shaTop0:bH,  paBBot = slBody?shaBot0:bL;
   double pa1Top = slBody?shaTop1:m1H, pa1Bot = slBody?shaBot1:m1L;
   double pa2Top = slBody?shaTop2:m2H, pa2Bot = slBody?shaBot2:m2L;

   bool _ab=(rawC>paBTop), _a1=(rawC>pa1Top), _a2=(rawC>pa2Top);
   bool _bb=(rawC<paBBot), _b1=(rawC<pa1Bot), _b2=(rawC<pa2Bot);
   int nAbove=(_ab?1:0)+(_a1?1:0)+(_a2?1:0);
   int nBelow=(_bb?1:0)+(_b1?1:0)+(_b2?1:0);

   bool allBull=false, allBear=false;
   switch(PaLayers)
     {
      case PA_ALL3:     allBull=(_ab&&_a1&&_a2); allBear=(_bb&&_b1&&_b2); break;
      case PA_H1H2:     allBull=(_a1&&_a2);      allBear=(_b1&&_b2);      break;
      case PA_B_H1:     allBull=(_ab&&_a1);      allBear=(_bb&&_b1);      break;
      case PA_B_H2:     allBull=(_ab&&_a2);      allBear=(_bb&&_b2);      break;
      case PA_H2ONLY:   allBull=_a2;             allBear=_b2;             break;
      case PA_H1ONLY:   allBull=_a1;             allBear=_b1;             break;
      case PA_BASEONLY: allBull=_ab;             allBear=_bb;             break;
      default:          allBull=(nAbove>=2);     allBear=(nBelow>=2);     break;
     }

   bool paBullRaw = (ConfirmMode==CF_1BAR) ? (g_allBull1 && !g_allBull2) : (allBull && !g_allBull1);
   bool paBearRaw = (ConfirmMode==CF_1BAR) ? (g_allBear1 && !g_allBear2) : (allBear && !g_allBear1);

   //--- gap filter (see deviation 2: reproduces the Pine's lookahead_off read)
   int dsh  = iBarShift(Symbol(),PERIOD_D1,Time[i],false);
   int duse = HTF_UseDevelopingBar ? dsh : dsh+1;
   double dayOpen   = (dsh>=0) ? iOpen(Symbol(),PERIOD_D1,duse)    : 0.0;
   double dayPClose = (dsh>=0) ? iClose(Symbol(),PERIOD_D1,duse+1) : 0.0;
   double gapPct = (dayOpen>0.0 && dayPClose>0.0)
                 ? MathAbs(dayOpen-dayPClose)/dayPClose*100.0 : 0.0;
   bool isNewDay = false;
   if(i+1 < Bars) isNewDay = (iBarShift(Symbol(),PERIOD_D1,Time[i],false)
                           != iBarShift(Symbol(),PERIOD_D1,Time[i+1],false));
   bool gapBlock = (GapThresh>0.0 && isNewDay && gapPct>GapThresh);

   //--- last-bar-beyond anchors
   double pxLowTest  = slBody?MathMin(rawO,rawC):rawL;
   double pxHighTest = slBody?MathMax(rawO,rawC):rawH;
   double haLowTest  = slBody?shaBot0:bL;
   double haHighTest = slBody?shaTop0:bH;
   double h1BotEdge  = slBody?shaBot1:m1L;
   double h1TopEdge  = slBody?shaTop1:m1H;
   double h2BotEdge  = slBody?shaBot2:m2L;
   double h2TopEdge  = slBody?shaTop2:m2H;

   if(pxLowTest  < h1BotEdge) g_xlPxH1 = pxLowTest;
   if(pxLowTest  < h2BotEdge) g_xlPxH2 = pxLowTest;
   if(haLowTest  < h1BotEdge) g_xlHaH1 = haLowTest;
   if(haLowTest  < h2BotEdge) g_xlHaH2 = haLowTest;
   if(pxHighTest > h1TopEdge) g_xhPxH1 = pxHighTest;
   if(pxHighTest > h2TopEdge) g_xhPxH2 = pxHighTest;
   if(haHighTest > h1TopEdge) g_xhHaH1 = haHighTest;
   if(haHighTest > h2TopEdge) g_xhHaH2 = haHighTest;

   bool nearIsH1Long  = (MathAbs(rawC-h1BotEdge) <= MathAbs(rawC-h2BotEdge));
   bool nearIsH1Short = (MathAbs(rawC-h1TopEdge) <= MathAbs(rawC-h2TopEdge));

   //--- session / date
   int nowMin = TimeHour(Time[i])*60 + TimeMinute(Time[i]);
   int eodMin = EodHour*60 + EodMinute;
   bool pastCutoff     = (UseEod && nowMin>=eodMin);
   bool eodEntryBlock  = (pastCutoff && EodBlockEntries);
   bool inDate = (!UseDate) || (Time[i]>=DateStart && Time[i]<=DateEnd);

   //--- eligibility and arming
   if(g_posDir=="long")
     {
      g_eligB = g_eligB || _ab;  g_elig1 = g_elig1 || _a1;  g_elig2 = g_elig2 || _a2;
      g_armB  = g_armB  || baseBullBar;
      g_arm1  = g_arm1  || htf1BullBar;
      g_arm2  = g_arm2  || htf2BullBar;
     }
   else if(g_posDir=="short")
     {
      g_eligB = g_eligB || _bb;  g_elig1 = g_elig1 || _b1;  g_elig2 = g_elig2 || _b2;
      g_armB  = g_armB  || !baseBullBar;
      g_arm1  = g_arm1  || !htf1BullBar;
      g_arm2  = g_arm2  || !htf2BullBar;
     }

   double ikNearL,ikMidL,ikFarL, ikNearS,ikMidS,ikFarS;
   double rkNearL,rkMidL,rkFarL, rkNearS,rkMidS,rkFarS;
   FRank(_ab,shaBot0,_a1,shaBot1,_a2,shaBot2,rawC,ikNearL,ikMidL,ikFarL);
   FRank(_bb,shaTop0,_b1,shaTop1,_b2,shaTop2,rawC,ikNearS,ikMidS,ikFarS);
   FRank(g_eligB,shaBot0,g_elig1,shaBot1,g_elig2,shaBot2,rawC,rkNearL,rkMidL,rkFarL);
   FRank(g_eligB,shaTop0,g_elig1,shaTop1,g_elig2,shaTop2,rawC,rkNearS,rkMidS,rkFarS);

   //--- swing levels
   double swLowLvl   = slBody?LowestBodyAt(i,SlLookback) :LowestWickAt(i,SlLookback);
   double swHighLvl  = slBody?HighestBodyAt(i,SlLookback):HighestWickAt(i,SlLookback);
   double trigLowLvl = slBody?MathMin(rawO,rawC):rawL;
   double trigHighLvl= slBody?MathMax(rawO,rawC):rawH;
   double slBufRaw   = DistRaw(SlBufferPct,SlBufferPips,rawC);
   double minStopRaw = DistRaw(MinStopPct,MinStopPips,rawC);
   double beOffRaw   = DistRaw(BeOffsetPct,BeOffsetPips,rawC);
   double spreadRaw  = SpreadRaw();

   //--- trail anchors
   bool trBody = (TrailPriceBasis==BS_BODY);
   double trSwLow  = trBody?LowestBodyAt(i,TrailLookback) :LowestWickAt(i,TrailLookback);
   double trSwHigh = trBody?HighestBodyAt(i,TrailLookback):HighestWickAt(i,TrailLookback);
   double trLowAnchor=NA, trHighAnchor=NA;
   switch(TrailMode)
     {
      case TR_SWING:   trLowAnchor=trSwLow;  trHighAnchor=trSwHigh;  break;
      case TR_BASE:    trLowAnchor=shaBot0;  trHighAnchor=shaTop0;   break;
      case TR_HTF1:    trLowAnchor=shaBot1;  trHighAnchor=shaTop1;   break;
      case TR_HTF2:    trLowAnchor=shaBot2;  trHighAnchor=shaTop2;   break;
      case TR_EL_NEAR: trLowAnchor=rkNearL;  trHighAnchor=rkNearS;   break;
      case TR_EL_MID:  trLowAnchor=rkMidL;   trHighAnchor=rkMidS;    break;
      default:         trLowAnchor=rkFarL;   trHighAnchor=rkFarS;    break;
     }
   double trBufRaw = DistRaw(TrailBufferPct,TrailBufferPips,rawC);
   double trLowRef  = OK(trLowAnchor) ? trLowAnchor - trBufRaw : NA;
   double trHighRef = OK(trHighAnchor)? trHighAnchor + trBufRaw: NA;

   bool crossDn = (OK(g_prevBaseC) && OK(g_prevH1C) && g_prevBaseC>g_prevH1C && bC<m1C);
   bool crossUp = (OK(g_prevBaseC) && OK(g_prevH1C) && g_prevBaseC<g_prevH1C && bC>m1C);

   double shabBot = (ShaBreakLayer==LY_BASE)?shaBot0:(ShaBreakLayer==LY_HTF1)?shaBot1:shaBot2;
   double shabTop = (ShaBreakLayer==LY_BASE)?shaTop0:(ShaBreakLayer==LY_HTF1)?shaTop1:shaTop2;

   //--- layer-flip condition: eligible AND armed AND now against the trade
   bool flipBL=(g_eligB&&g_armB&&!baseBullBar), flip1L=(g_elig1&&g_arm1&&!htf1BullBar), flip2L=(g_elig2&&g_arm2&&!htf2BullBar);
   bool flipBS=(g_eligB&&g_armB&& baseBullBar), flip1S=(g_elig1&&g_arm1&& htf1BullBar), flip2S=(g_elig2&&g_arm2&& htf2BullBar);
   int nElig     = (g_eligB?1:0)+(g_elig1?1:0)+(g_elig2?1:0);
   int nFlipLong = (flipBL?1:0)+(flip1L?1:0)+(flip2L?1:0);
   int nFlipShrt = (flipBS?1:0)+(flip1S?1:0)+(flip2S?1:0);

   bool alignBrokenLong=false, alignBrokenShort=false;
   switch(AlignBreakLevel)
     {
      case FL_BASE: alignBrokenLong=flipBL; alignBrokenShort=flipBS; break;
      case FL_HTF1: alignBrokenLong=flip1L; alignBrokenShort=flip1S; break;
      case FL_HTF2: alignBrokenLong=flip2L; alignBrokenShort=flip2S; break;
      case FL_ANY:  alignBrokenLong=(nFlipLong>0); alignBrokenShort=(nFlipShrt>0); break;
      default:      alignBrokenLong=(nElig>0 && nFlipLong==nElig);
                    alignBrokenShort=(nElig>0 && nFlipShrt==nElig); break;
     }

   string posDirPrev = g_posDir;
   bool evEntryLong=false, evEntryShort=false, evStopHit=false, evAlignBreak=false;
   string stoppedFrom = "";

   //================= manage the open hypothetical position ================
   if(g_posDir=="long" && !IsNA(g_stopLevel))
     {
      double _r = (g_riskUnit>0.0) ? (rawC-g_entryPrice)/g_riskUnit : 0.0;
      if(UseBE && !g_beMoved && _r>=BeTriggerR)
        { g_stopLevel=MathMax(g_stopLevel,g_entryPrice+beOffRaw); g_beMoved=true; }
      if(UseTrail && _r>=TrailStartR && OK(trLowRef))
         g_stopLevel=MathMax(g_stopLevel,trLowRef);
      g_peakR = MathMax(g_peakR,_r);
      g_badBars = alignBrokenLong ? g_badBars+1 : 0;

      bool alignOut = (UseAlignExit && g_badBars>=AlignConfirmBars);
      bool other = (alignOut
                 || (UseShaBreak && rawC<shabBot)
                 || (UseTarget   && _r>=TargetR)
                 || (UseGiveback && g_peakR>=GivebackMinR && _r<=g_peakR*(1.0-GivebackPct/100.0))
                 || (UseTimeStop && g_entryAbs>=0 && (g_absBar-g_entryAbs)>=TimeStopBars && _r<TimeStopMinR)
                 || (UseCrossExit && crossDn)) || pastCutoff;
      bool stopHit = UseHardStop ? (rawL<=g_stopLevel) : (rawC<=g_stopLevel);

      if(stopHit || other)
        {
         evStopHit    = stopHit;
         evAlignBreak = (other && !stopHit);
         if(stopHit) stoppedFrom = "long";
         g_rearmHigh=rawC; g_rearmLow=NA;
         g_posDir="flat";
         g_eligB=false; g_elig1=false; g_elig2=false;
         g_armB=false;  g_arm1=false;  g_arm2=false;
         g_entryPrice=NA; g_stopLevel=NA; g_riskUnit=NA;
         g_beMoved=false; g_badBars=0; g_peakR=0.0;
        }
     }
   else if(g_posDir=="short" && !IsNA(g_stopLevel))
     {
      double _r = (g_riskUnit>0.0) ? (g_entryPrice-rawC)/g_riskUnit : 0.0;
      if(UseBE && !g_beMoved && _r>=BeTriggerR)
        { g_stopLevel=MathMin(g_stopLevel,g_entryPrice-beOffRaw); g_beMoved=true; }
      if(UseTrail && _r>=TrailStartR && OK(trHighRef))
         g_stopLevel=MathMin(g_stopLevel,trHighRef);
      g_peakR = MathMax(g_peakR,_r);
      g_badBars = alignBrokenShort ? g_badBars+1 : 0;

      bool alignOut2 = (UseAlignExit && g_badBars>=AlignConfirmBars);
      bool other2 = (alignOut2
                  || (UseShaBreak && rawC>shabTop)
                  || (UseTarget   && _r>=TargetR)
                  || (UseGiveback && g_peakR>=GivebackMinR && _r<=g_peakR*(1.0-GivebackPct/100.0))
                  || (UseTimeStop && g_entryAbs>=0 && (g_absBar-g_entryAbs)>=TimeStopBars && _r<TimeStopMinR)
                  || (UseCrossExit && crossUp)) || pastCutoff;
      //  bid + spread = ask, which is what actually fills a short's stop
      bool stopHit2 = UseHardStop ? (rawH+spreadRaw>=g_stopLevel)
                                  : (rawC+spreadRaw>=g_stopLevel);

      if(stopHit2 || other2)
        {
         evStopHit    = stopHit2;
         evAlignBreak = (other2 && !stopHit2);
         if(stopHit2) stoppedFrom = "short";
         g_rearmLow=rawC; g_rearmHigh=NA;
         g_posDir="flat";
         g_eligB=false; g_elig1=false; g_elig2=false;
         g_armB=false;  g_arm1=false;  g_arm2=false;
         g_entryPrice=NA; g_stopLevel=NA; g_riskUnit=NA;
         g_beMoved=false; g_badBars=0; g_peakR=0.0;
        }
     }

   //================= re-entry reference level =============================
   if(!IsNA(g_rearmHigh) && g_allBull1 && !allBull) g_rearmHigh = rawC;
   if(!IsNA(g_rearmLow)  && g_allBear1 && !allBear) g_rearmLow  = rawC;

   double rexBot = (ReentryLayer==LY_BASE)?shaBot0:(ReentryLayer==LY_HTF1)?shaBot1:shaBot2;
   double rexTop = (ReentryLayer==LY_BASE)?shaTop0:(ReentryLayer==LY_HTF1)?shaTop1:shaTop2;
   bool rawIsBull = (rawC>rawO);
   bool rawIsBear = (rawC<rawO);

   if(IsNA(g_rearmHigh) || !allBull) g_trigHigh = NA;
   else if(IsNA(g_trigHigh) && rawIsBull && rawC>rexTop) g_trigHigh = rawH;

   if(IsNA(g_rearmLow) || !allBear) g_trigLow = NA;
   else if(IsNA(g_trigLow) && rawIsBear && rawC<rexBot) g_trigLow = rawL;

   bool patLong  = (!IsNA(g_trigHigh) && rawIsBull && rawC>g_trigHigh);
   bool patShort = (!IsNA(g_trigLow)  && rawIsBear && rawC<g_trigLow);
   bool refLong  = (!IsNA(g_rearmHigh) && rawC>g_rearmHigh && (!ReentryNeedsBase || allBull));
   bool refShort = (!IsNA(g_rearmLow)  && rawC<g_rearmLow  && (!ReentryNeedsBase || allBear));
   bool reLong   = UseReentry && ((ReentryStyle==RE_PATTERN)?patLong :refLong);
   bool reShort  = UseReentry && ((ReentryStyle==RE_PATTERN)?patShort:refShort);

   bool longSignal  = AllowLongs  && (paBullRaw||reLong)  && inDate && !gapBlock && !eodEntryBlock && (!EntryNeedsDir||rawIsBull);
   bool shortSignal = AllowShorts && (paBearRaw||reShort) && inDate && !gapBlock && !eodEntryBlock && (!EntryNeedsDir||rawIsBear);
   bool revLong  = ReverseOnStop && stoppedFrom=="short" && allBull && AllowLongs  && inDate && !gapBlock && !eodEntryBlock && (!EntryNeedsDir||rawIsBull);
   bool revShort = ReverseOnStop && stoppedFrom=="long"  && allBear && AllowShorts && inDate && !gapBlock && !eodEntryBlock && (!EntryNeedsDir||rawIsBear);

   //================= entries =============================================
   if(g_posDir=="flat" && (longSignal||revLong))
     {
      double lvl = swLowLvl;
      switch(SlMode)
        {
         case SL_TRIGGER:   lvl=trigLowLvl; break;
         case SL_SWING:     lvl=swLowLvl;   break;
         case SL_BASE:      lvl=shaBot0;    break;
         case SL_HTF1:      lvl=shaBot1;    break;
         case SL_HTF2:      lvl=shaBot2;    break;
         case SL_LBAR_NEAR: { double v=nearIsH1Long?g_xlPxH1:g_xlPxH2; lvl=IsNA(v)?swLowLvl:v; } break;
         case SL_LBAR_FAR:  { double v=nearIsH1Long?g_xlPxH2:g_xlPxH1; lvl=IsNA(v)?swLowLvl:v; } break;
         case SL_LSHA_NEAR: { double v=nearIsH1Long?g_xlHaH1:g_xlHaH2; lvl=IsNA(v)?swLowLvl:v; } break;
         case SL_LSHA_FAR:  { double v=nearIsH1Long?g_xlHaH2:g_xlHaH1; lvl=IsNA(v)?swLowLvl:v; } break;
         case SL_EL_NEAR:   lvl=OK(ikNearL)?ikNearL:swLowLvl; break;
         case SL_EL_MID:    lvl=OK(ikMidL) ?ikMidL :swLowLvl; break;
         case SL_EL_FAR:    lvl=OK(ikFarL) ?ikFarL :swLowLvl; break;
        }
      double s = lvl - slBufRaw;
      if(minStopRaw>0.0) s = MathMin(s, rawC-minStopRaw);

      if(s < rawC)
        {
         g_eligB=_ab; g_elig1=_a1; g_elig2=_a2;
         g_armB=baseBullBar; g_arm1=htf1BullBar; g_arm2=htf2BullBar;
         g_posDir="long"; g_entryPrice=rawC; g_lblEntryPx=rawC;
         g_stopLevel=s; g_riskUnit=rawC-s;
         g_beMoved=false; g_badBars=0; g_peakR=0.0; g_entryAbs=g_absBar;
         g_rearmHigh=NA; g_rearmLow=NA;
         evEntryLong=true;
        }
     }
   else if(g_posDir=="flat" && (shortSignal||revShort))
     {
      double lvlS = swHighLvl;
      switch(SlMode)
        {
         case SL_TRIGGER:   lvlS=trigHighLvl; break;
         case SL_SWING:     lvlS=swHighLvl;   break;
         case SL_BASE:      lvlS=shaTop0;     break;
         case SL_HTF1:      lvlS=shaTop1;     break;
         case SL_HTF2:      lvlS=shaTop2;     break;
         case SL_LBAR_NEAR: { double w=nearIsH1Short?g_xhPxH1:g_xhPxH2; lvlS=IsNA(w)?swHighLvl:w; } break;
         case SL_LBAR_FAR:  { double w=nearIsH1Short?g_xhPxH2:g_xhPxH1; lvlS=IsNA(w)?swHighLvl:w; } break;
         case SL_LSHA_NEAR: { double w=nearIsH1Short?g_xhHaH1:g_xhHaH2; lvlS=IsNA(w)?swHighLvl:w; } break;
         case SL_LSHA_FAR:  { double w=nearIsH1Short?g_xhHaH2:g_xhHaH1; lvlS=IsNA(w)?swHighLvl:w; } break;
         case SL_EL_NEAR:   lvlS=OK(ikNearS)?ikNearS:swHighLvl; break;
         case SL_EL_MID:    lvlS=OK(ikMidS) ?ikMidS :swHighLvl; break;
         case SL_EL_FAR:    lvlS=OK(ikFarS) ?ikFarS :swHighLvl; break;
        }
      double s2 = lvlS + slBufRaw;
      if(minStopRaw>0.0) s2 = MathMax(s2, rawC+minStopRaw);

      if(s2 > rawC)
        {
         g_eligB=_bb; g_elig1=_b1; g_elig2=_b2;
         g_armB=!baseBullBar; g_arm1=!htf1BullBar; g_arm2=!htf2BullBar;
         g_posDir="short"; g_entryPrice=rawC; g_lblEntryPx=rawC;
         g_stopLevel=s2; g_riskUnit=s2-rawC;
         g_beMoved=false; g_badBars=0; g_peakR=0.0; g_entryAbs=g_absBar;
         g_rearmHigh=NA; g_rearmLow=NA;
         evEntryShort=true;
        }
     }

   //================= alert / marker gating ===============================
   bool rawLong  = AllowLongs  && (paBullRaw||reLong)  && inDate && !gapBlock && !eodEntryBlock && (!EntryNeedsDir||rawIsBull);
   bool rawShort = AllowShorts && (paBearRaw||reShort) && inDate && !gapBlock && !eodEntryBlock && (!EntryNeedsDir||rawIsBear);

   bool fireEntryLong  = AlEntry && (AlSignalOnly?rawLong :evEntryLong);
   bool fireEntryShort = AlEntry && (AlSignalOnly?rawShort:evEntryShort);
   bool fireAlignBreak = AlExit && evAlignBreak;
   bool fireStopHit    = AlStop && evStopHit;

   //--- markers and labels
   if(i <= MaxMarkerBars)
     {
      double off = rawC*LabelOffsetPct/100.0;
      string tag = OBJPREFIX + IntegerToString((int)Time[i]);
      if(ShowMarks && fireEntryLong)  MakeArrow(tag+"_EL",Time[i],rawL-off*0.5,233,ColBull,2);
      if(ShowMarks && fireEntryShort) MakeArrow(tag+"_ES",Time[i],rawH+off*0.5,234,ColBear,2);
      if(ShowMarks && fireStopHit)    MakeArrow(tag+"_SX",Time[i],rawC,251,ColStop,2);
      if(ShowMarks && fireAlignBreak) MakeArrow(tag+"_AX",Time[i],rawC,251,ColExit,2);

      if(ShowPriceLabels && (fireEntryLong||fireEntryShort))
        {
         bool up = fireEntryLong;
         MakeText(tag+"_LT",Time[i],up?rawL-off:rawH+off,
                  (up?"LONG ":"SHORT ")+DoubleToString(rawC,Digits),
                  up?ColBull:ColBear,(int)LabelSize);
        }
      if(ShowPriceLabels && (fireStopHit||fireAlignBreak))
        {
         bool wasUp = (posDirPrev=="long");
         string why = fireStopHit?"STOP ":"EXIT ";
         string from = IsNA(g_lblEntryPx)?"":("  (from "+DoubleToString(g_lblEntryPx,Digits)+")");
         MakeText(tag+"_XT",Time[i],wasUp?rawH+off:rawL-off,
                  why+DoubleToString(rawC,Digits)+from,
                  fireStopHit?ColStop:ColExit,(int)LabelSize);
        }
     }

   //--- alerts, most recently closed bar only, never during history load
   if(live)
     {
      string head = "3SHA-PA "+Symbol()+" "+IntegerToString(Period())+"M @ "+DoubleToString(rawC,Digits);
      if(fireEntryLong)  FireAlert(head+" — LONG entry");
      if(fireEntryShort) FireAlert(head+" — SHORT entry");
      if(fireAlignBreak) FireAlert(head+" — exit signal (alignment / target / give-back / time / SHA break)");
      if(fireStopHit)    FireAlert(head+" — STOP hit, exit");
     }

   //--- carry state forward
   b_stop[i]  = (g_posDir!="flat" && !IsNA(g_stopLevel)) ? g_stopLevel : EMPTY_VALUE;
   b_state[i] = (g_posDir=="long") ? 1.0 : (g_posDir=="short") ? -1.0 : 0.0;

   g_allBull2=g_allBull1; g_allBull1=allBull;
   g_allBear2=g_allBear1; g_allBear1=allBear;
   g_prevBaseC=bC; g_prevH1C=m1C;
  }

//====================================================================
// MAIN
//====================================================================
int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
  {
   if(rates_total < 200) return(0);

   //--- rebuild the higher-timeframe SHA series when a new HTF bar appears
   datetime t1 = iTime(Symbol(),Htf1TF,0);
   if(t1!=h1Stamp || h1Count==0)
      if(BuildLayerSHA(Htf1TF,Htf1Len1,Htf1Len2,h1O,h1H,h1L,h1C,h1Count)) h1Stamp=t1;
   datetime t2 = iTime(Symbol(),Htf2TF,0);
   if(t2!=h2Stamp || h2Count==0)
      if(BuildLayerSHA(Htf2TF,Htf2Len1,Htf2Len2,h2O,h2H,h2L,h2C,h2Count)) h2Stamp=t2;

   if(h1Count==0 || h2Count==0)
     {
      Comment("3SHA-PA: waiting for higher-timeframe history. Open the HTF chart once to force a download.");
      return(0);
     }

   //--- decide how far back to recompute
   int  startIdx;
   bool seedRun;
   if(prev_calculated<=0)
     {
      ResetState();
      ClearObjects();
      startIdx = rates_total-1;
      if(MaxBars>0 && MaxBars<startIdx) startIdx = MaxBars;
      seedRun = true;
      for(int z=rates_total-1; z>startIdx; z--)
        {
         b_h2A[z]=EMPTY_VALUE; b_h2B[z]=EMPTY_VALUE;
         b_h1A[z]=EMPTY_VALUE; b_h1B[z]=EMPTY_VALUE;
         b_bsA[z]=EMPTY_VALUE; b_bsB[z]=EMPTY_VALUE;
         b_stop[z]=EMPTY_VALUE; b_state[z]=0.0;
         c_bC1[z]=EMPTY_VALUE; c_bC2[z]=EMPTY_VALUE;
         c_m1O[z]=EMPTY_VALUE; c_m1C[z]=EMPTY_VALUE;
         c_m2O[z]=EMPTY_VALUE; c_m2C[z]=EMPTY_VALUE;
        }
     }
   else
     {
      startIdx = rates_total - prev_calculated + 1;
      seedRun  = false;
     }
   if(startIdx > rates_total-1) startIdx = rates_total-1;
   if(startIdx < 0) startIdx = 0;

   //--- base SHA on the chart timeframe, plus the HTF mapping, per bar
   double a1 = 2.0/(BaseLen1+1.0);
   double a2 = 2.0/(BaseLen2+1.0);

   for(int i=startIdx; i>=0; i--)
     {
      bool seed = (i>=rates_total-1) || (seedRun && i==startIdx) || !OK(c_bC1[i+1]);
      double O=Open[i], H=High[i], L=Low[i], C=Close[i];
      double o1,h1v,l1v,c1v,haC,haO,haH,haL,o2,h2v,l2v,c2v;

      if(seed) { o1=O; h1v=H; l1v=L; c1v=C; }
      else
        {
         o1  = a1*O + (1.0-a1)*c_bO1[i+1];
         h1v = a1*H + (1.0-a1)*c_bH1[i+1];
         l1v = a1*L + (1.0-a1)*c_bL1[i+1];
         c1v = a1*C + (1.0-a1)*c_bC1[i+1];
        }

      haC = (o1+h1v+l1v+c1v)/4.0;
      haO = seed ? (o1+c1v)/2.0 : (c_bHaO[i+1]+c_bHaC[i+1])/2.0;
      haH = MathMax(h1v,MathMax(haO,haC));
      haL = MathMin(l1v,MathMin(haO,haC));

      if(seed) { o2=haO; h2v=haH; l2v=haL; c2v=haC; }
      else
        {
         o2  = a2*haO + (1.0-a2)*c_bO2[i+1];
         h2v = a2*haH + (1.0-a2)*c_bH2[i+1];
         l2v = a2*haL + (1.0-a2)*c_bL2[i+1];
         c2v = a2*haC + (1.0-a2)*c_bC2[i+1];
        }

      c_bO1[i]=o1;  c_bH1[i]=h1v; c_bL1[i]=l1v; c_bC1[i]=c1v;
      c_bHaO[i]=haO; c_bHaC[i]=haC;
      c_bO2[i]=o2;  c_bH2[i]=h2v; c_bL2[i]=l2v; c_bC2[i]=c2v;

      double mo,mh,ml,mc;
      if(MapHTF(i,Htf1TF,h1O,h1H,h1L,h1C,h1Count,mo,mh,ml,mc))
        { c_m1O[i]=mo; c_m1H[i]=mh; c_m1L[i]=ml; c_m1C[i]=mc; }
      else
        { c_m1O[i]=EMPTY_VALUE; c_m1H[i]=EMPTY_VALUE; c_m1L[i]=EMPTY_VALUE; c_m1C[i]=EMPTY_VALUE; }

      if(MapHTF(i,Htf2TF,h2O,h2H,h2L,h2C,h2Count,mo,mh,ml,mc))
        { c_m2O[i]=mo; c_m2H[i]=mh; c_m2L[i]=ml; c_m2C[i]=mc; }
      else
        { c_m2O[i]=EMPTY_VALUE; c_m2H[i]=EMPTY_VALUE; c_m2L[i]=EMPTY_VALUE; c_m2C[i]=EMPTY_VALUE; }

      //--- candle bodies. A = open, B = close (see the colour note in OnInit)
      if(Htf2Show && OK(c_m2O[i]) && OK(c_m2C[i]))
        { b_h2A[i]=c_m2O[i]; b_h2B[i]=c_m2C[i]; }
      else { b_h2A[i]=EMPTY_VALUE; b_h2B[i]=EMPTY_VALUE; }

      if(Htf1Show && OK(c_m1O[i]) && OK(c_m1C[i]))
        { b_h1A[i]=c_m1O[i]; b_h1B[i]=c_m1C[i]; }
      else { b_h1A[i]=EMPTY_VALUE; b_h1B[i]=EMPTY_VALUE; }

      if(BaseShow) { b_bsA[i]=o2; b_bsB[i]=c2v; }
      else { b_bsA[i]=EMPTY_VALUE; b_bsB[i]=EMPTY_VALUE; }
     }

   //--- state machine: closed bars only, each bar exactly once
   int  smStart;
   bool firstRun = (g_lastProcTime==0);
   if(firstRun)
      smStart = MathMin(startIdx-1, rates_total-2);
   else
     {
      int sh = iBarShift(Symbol(),0,g_lastProcTime,true);
      if(sh<0)                       // history rebuilt under us: start clean
        {
         ResetState();
         ClearObjects();
         return(0);
        }
      smStart = sh-1;
     }
   if(smStart > rates_total-2) smStart = rates_total-2;

   for(int i=smStart; i>=1; i--)
      ProcessBar(i, (!firstRun && i==1));

   if(smStart>=1) g_lastProcTime = Time[1];
   g_firstPass = false;

   //--- bar 0 is drawn but never signals
   b_stop[0]  = (ShowStop && g_posDir!="flat" && !IsNA(g_stopLevel)) ? g_stopLevel : EMPTY_VALUE;
   b_state[0] = (g_posDir=="long") ? 1.0 : (g_posDir=="short") ? -1.0 : 0.0;

   bool pbBase = (OK(c_bO2[1]) && OK(c_bC2[1]) && c_bC2[1]>=c_bO2[1]);
   bool pbHtf1 = (OK(c_m1O[1]) && OK(c_m1C[1]) && c_m1C[1]>=c_m1O[1]);
   bool pbHtf2 = (OK(c_m2O[1]) && OK(c_m2C[1]) && c_m2C[1]>=c_m2O[1]);
   DrawPanel(pbBase,pbHtf1,pbHtf2);

   return(rates_total);
  }
//+------------------------------------------------------------------+
