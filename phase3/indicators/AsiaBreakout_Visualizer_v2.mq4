//+------------------------------------------------------------------+
//|                                  AsiaBreakout_Visualizer_v2.mq4  |
//|          History visualiser for AsiaBreakout_EA_v2 - every past   |
//|          setup, entry, scaled exit and stop the EA would have had |
//+------------------------------------------------------------------+
//
//  WHAT THIS IS
//    The EA's rules, replayed over history and drawn on the chart.
//
//      shaded box      the range being broken
//      arrow           the entry, on the bar the trade would have opened
//      green dot       the point the target was touched and part was taken
//      thick line      the trade, entry to final exit, coloured by outcome
//      dotted lines    the target and the structural stop
//      label           the blended R multiple and how it ended
//
//  v2 MATCHES EA v2
//    - one candle size measures the Asia range AND provides the breakout
//      close and the stop close; the trigger candle keeps its own
//    - scaled exit: a slice at the target on TOUCH, the runner to the NY
//      close, with the close-based stop still governing the runner
//    - repeat entries: up to InpMaxTradesPerDay a day, at most one open per
//      direction, so a long and a short can be live together
//
//  THE HISTORY BUG THIS VERSION FIXES
//    v1 built the replay once, inside OnInit. At that moment MT4 has usually
//    not loaded the OTHER timeframes the replay reads - the range timeframe
//    and the daily bars behind the ATR. Those reads failed, so nearly every
//    day was discarded as "no data", and the next rebuild attempt did not
//    come until a new signal bar closed - up to an hour later on H1. The
//    result looked like an indicator that only knew about the last day or
//    two, which is exactly what it was.
//
//    v2 watches how many bars each timeframe has and rebuilds whenever that
//    number grows, so the picture fills in as MT4 streams the history down.
//    The panel reports the depth of every timeframe it depends on, and says
//    plainly when history is the thing limiting the replay rather than the
//    rules.
//
//  WHAT IT CANNOT KNOW
//    Historical spread, slippage and swap. Entries are drawn at the raw bar
//    open and exits at the raw level, so the R multiples here are kinder
//    than live trading. InpMaxSpreadPoints is therefore not applied.
//
//  NOTHING REPAINTS
//    Only closed bars are read.
//
//+------------------------------------------------------------------+
#property copyright "algo-trading-system"
#property link      "https://github.com/mesan4net-blip/algo-trading-system"
#property version   "2.00"
#property strict
#property indicator_chart_window
#property indicator_buffers 0

//+------------------------------------------------------------------+
//| Enumerations - identical to the EA's                             |
//+------------------------------------------------------------------+
enum ENUM_STRAT_MODE
  {
   MODE_ASIA_RANGE      = 0,  // Asia session range breakout
   MODE_TRIGGER_CANDLE  = 1,  // Trigger candle breakout
   MODE_BOTH            = 2   // Both
  };

enum ENUM_TZ
  {
   TZ_BROKER  = 0,  // Broker server time
   TZ_UTC     = 1,  // UTC / GMT (no DST)
   TZ_LONDON  = 2,  // London (GMT/BST, EU DST rules)
   TZ_NEWYORK = 3,  // New York (EST/EDT, US DST rules)
   TZ_TOKYO   = 4   // Tokyo (JST, no DST)
  };

enum ENUM_DST_RULE
  {
   DST_NONE = 0,  // Broker clock does not shift
   DST_US   = 1,  // Broker follows US/New York DST
   DST_EU   = 2   // Broker follows EU/London DST
  };

enum ENUM_OFFSET_MODE
  {
   BOFF_AUTO   = 0,  // Auto-detect from terminal
   BOFF_MANUAL = 1   // Use InpBrokerWinterOffsetHours
  };

enum ENUM_CANDLE_SL_SRC
  {
   CSL_TRIGGER_CANDLE = 0,  // Trigger candle low/high
   CSL_ASIA_SESSION   = 1   // Asia session low/high
  };

enum ENUM_REVERSAL_FROM
  {
   REV_FROM_LEVEL = 0,  // From the LEVEL that was broken (back inside the range)
   REV_FROM_ENTRY = 1,  // From the ENTRY price
   REV_FROM_PEAK  = 2   // From the BEST price reached (giveback)
  };

enum ENUM_STOP_STYLE
  {
   STOP_ON_CLOSE = 0,  // Exit when a signal bar CLOSES beyond the level
   STOP_ON_TOUCH = 1   // Stop sits AT the level and fills on a touch
  };

#define DIR_NONE   0
#define DIR_LONG   1
#define DIR_SHORT -1

#define DX_LONG    0
#define DX_SHORT   1
#define DX_COUNT   2

#define SLOT_ASIA    0
#define SLOT_TRIGGER 1
#define SLOT_COUNT   2

#define OBJ_PREFIX "ABVIZ_"

#define EXIT_TARGET  0
#define EXIT_STOP    1
#define EXIT_NYCLOSE 2
#define EXIT_REVERSE 3

//+------------------------------------------------------------------+
//| Inputs - keep these identical to your EA                         |
//+------------------------------------------------------------------+
input string          _s01                       = "=== STRATEGY ===";          // .
input ENUM_STRAT_MODE InpMode                    = MODE_ASIA_RANGE;             // Which breakout to replay
input double          InpTPPctOfATR              = 80.0;                        // Target as % of 5-day ATR
input ENUM_STOP_STYLE InpStopStyle               = STOP_ON_CLOSE;               // How the structural stop is honoured
input bool            InpTradeLongs              = true;                        // Replay long breakouts
input bool            InpTradeShorts             = true;                        // Replay short breakouts

input string          _s02                       = "=== TIMEFRAMES ===";        // .
input ENUM_TIMEFRAMES InpEntryTF                 = PERIOD_H1;                   // ASIA RANGE + BREAKOUT / ENTRY / STOP candle
input ENUM_TIMEFRAMES InpTriggerTF               = PERIOD_H1;                   // TRIGGER CANDLE candle

input string          _s03                       = "=== ASIA SESSION ===";      // .
input ENUM_TZ         InpAsiaTZ                  = TZ_UTC;                      // Timezone the Asia hours are given in
input int             InpAsiaStartHour           = 22;                          // Asia start hour
input int             InpAsiaStartMin            = 0;                           // Asia start minute
input int             InpAsiaEndHour             = 9;                           // Asia end hour
input int             InpAsiaEndMin              = 0;                           // Asia end minute

input string          _s04                       = "=== TRIGGER CANDLE ===";    // .
input ENUM_TZ         InpTriggerTZ               = TZ_LONDON;                   // Timezone the trigger hour is given in
input int             InpTriggerHour             = 8;                           // Trigger candle OPEN hour
input int             InpTriggerMin              = 0;                           // Trigger candle OPEN minute
input ENUM_CANDLE_SL_SRC InpCandleSLSource       = CSL_TRIGGER_CANDLE;          // Candle mode: stop/target anchor source

input string          _s05                       = "=== SCALED EXIT ===";       // .
input double          InpPartialClosePct         = 50.0;                        // % of the position closed AT THE TARGET
input bool            InpMoveStopAfterPartial    = false;                       // After the partial, stop the runner at entry

input string          _s05b                      = "=== REVERSAL EXIT ===";     // .
input bool            InpUseReversalExit         = false;                       // Close the trade if price reverses
input double          InpReversalPctOfRange      = 50.0;                        // Reversal size, as % of the range
input ENUM_REVERSAL_FROM InpReversalFrom         = REV_FROM_LEVEL;              // Reversal measured from what

input string          _s06                       = "=== 5-DAY ATR ===";         // .
input int             InpATRDays                 = 5;                           // ATR lookback in daily bars
input bool            InpATRSkipSunday           = true;                        // Skip the broker's stunted Sunday bar

input string          _s07                       = "=== FILTERS ===";           // .
input int             InpBreakoutBufferPoints    = 0;                           // Extra points beyond level to confirm
input int             InpMinRangePoints          = 0;                           // Skip if range narrower than this (0=off)
input int             InpMaxRangePoints          = 0;                           // Skip if range wider than this (0=off)
input int             InpMaxSLPoints             = 0;                           // Skip if structural stop farther than this (0=off)
input int             InpNoNewTradesBeforeCloseM = 30;                          // No new entries within N min of NY close
input bool            InpTradeMon                = true;                        // Replay Monday
input bool            InpTradeTue                = true;                        // Replay Tuesday
input bool            InpTradeWed                = true;                        // Replay Wednesday
input bool            InpTradeThu                = true;                        // Replay Thursday
input bool            InpTradeFri                = true;                        // Replay Friday

input string          _s08                       = "=== TRADE CONTROL ===";     // .
input int             InpMaxTradesPerDay         = 4;                           // Max entries per flavor per day
input bool            InpRequireReset            = false;                       // Price must re-enter the range before re-arming

input string          _s09                       = "=== HARD EXIT (NY CLOSE) ==="; // .
input ENUM_TZ         InpNYCloseTZ               = TZ_NEWYORK;                  // Timezone the NY close is given in
input int             InpNYCloseHour             = 17;                          // NY close hour
input int             InpNYCloseMin              = 0;                           // NY close minute
input bool            InpFridayEarlyClose        = false;                       // Use a different close time on Friday
input int             InpFridayCloseHour         = 16;                          // Friday close hour
input int             InpFridayCloseMin          = 0;                           // Friday close minute

input string          _s10                       = "=== BROKER CLOCK ===";      // .
input ENUM_OFFSET_MODE InpBrokerOffsetMode       = BOFF_AUTO;                   // How to learn the server GMT offset
input int             InpBrokerWinterOffsetHours = 2;                           // Server offset from UTC in WINTER
input ENUM_DST_RULE   InpBrokerDSTRule           = DST_US;                      // Does the server clock shift, and how

input string          _s11                       = "=== DISPLAY ===";           // .
input int             InpDaysToShow              = 60;                          // Trading days to replay
input bool            InpIncludeToday            = true;                        // Also replay the day in progress
input bool            InpShowAsiaBox             = true;                        // Draw the Asia range box
input bool            InpShowTriggerBox          = true;                        // Draw the trigger candle box
input bool            InpShowLevels              = true;                        // Draw the stop and target lines
input bool            InpShowLabels              = true;                        // Label each trade with its R multiple
input bool            InpShowSkips               = true;                        // Mark days that were skipped, and why
input bool            InpShowPanel               = true;                        // Show the summary panel
input color           InpColorAsia               = C'40,60,90';                 // Asia box
input color           InpColorTrigger            = C'90,60,20';                 // Trigger candle box
input color           InpColorWin                = clrMediumSeaGreen;           // Target was reached
input color           InpColorLoss               = clrIndianRed;                // Stopped on a close
input color           InpColorFlat               = clrGoldenrod;                // Ran to the NY close
input color           InpColorReverse            = clrOrchid;                   // Closed by the reversal exit
input color           InpColorSkip               = clrDimGray;                  // Skipped day

input string          _sPanel                    = "=== PANEL LOOK ===";        // .
input int             InpPanelFontSize           = 10;                          // Panel font size
input string          InpPanelFont               = "Consolas";                  // Panel font (use a MONOSPACED one)
input color           InpPanelTextColor          = clrBlack;                    // Panel text colour
input color           InpPanelBgColor            = clrWhite;                    // Panel background colour
input color           InpPanelBorderColor        = clrSilver;                   // Panel border colour
input ENUM_BASE_CORNER InpPanelCorner            = CORNER_LEFT_UPPER;           // Which corner the panel sits in
input int             InpPanelX                  = 12;                          // Panel offset from that corner, across
input int             InpPanelY                  = 14;                          // Panel offset from that corner, down
input int             InpPanelWidthChars         = 0;                           // Fixed panel width in characters (0 = fit)
input bool            InpPanelShowToggle         = true;                        // Show the hide/show button

input string          _s12                       = "=== EXPORT ===";            // .
input bool            InpExportCSV               = false;                       // Write the replayed trades to a CSV
input string          InpTag                     = "AsiaBO";                    // Name used in logs and the CSV

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
int    g_brokerWinterOffsetSec = 0;
double g_pointsToPrice         = 0.0;
int    g_objCount              = 0;
double g_pipSize               = 0.0;
int    g_csvHandle             = INVALID_HANDLE;
string g_panelBlock            = "";

//--- history tracking: the fix for v1's "only the last two days" bug
int    g_lastBarCount          = 0;
int    g_daysWithData          = 0;
string g_historyReport         = "";

//--- per-slot tallies
int    g_nTrades[SLOT_COUNT];
int    g_nWins[SLOT_COUNT];
int    g_nLosses[SLOT_COUNT];
int    g_nFlat[SLOT_COUNT];
int    g_nReverse[SLOT_COUNT];
int    g_nPartials[SLOT_COUNT];
double g_sumR[SLOT_COUNT];
double g_sumPips[SLOT_COUNT];
double g_wonPips[SLOT_COUNT];
double g_lostPips[SLOT_COUNT];
double g_bestPips[SLOT_COUNT];
double g_worstPips[SLOT_COUNT];
double g_bestR[SLOT_COUNT];
double g_worstR[SLOT_COUNT];
int    g_nDays[SLOT_COUNT];
int    g_nSkipNoBreak[SLOT_COUNT];
int    g_nSkipTarget[SLOT_COUNT];
int    g_nSkipFilter[SLOT_COUNT];
int    g_nSkipNoData[SLOT_COUNT];
//+------------------------------------------------------------------+
//|                                                                  |
//|  TIME                                                            |
//|                                                                  |
//|  Everything here reduces to one idea: UTC is the only unambiguous |
//|  clock, so all reasoning happens in UTC and is converted outwards. |
//|                                                                  |
//|    session local time  <-- UTC -->  broker server time            |
//|                                                                  |
//|  DST transitions are defined in UTC terms, so evaluating them     |
//|  from a UTC instant is exact - there is no ambiguous hour.        |
//|  The one approximation is broker -> UTC, which must guess the     |
//|  broker's own DST state before it knows the UTC instant. That is  |
//|  ambiguous only inside the one-hour transition band, which falls  |
//|  at 02:00 New York on a Sunday - the market is shut.              |
//+------------------------------------------------------------------+

//--- build a datetime from calendar fields (no timezone attached)
datetime MakeStamp(const int year, const int mon, const int day,
                   const int hour, const int min)
  {
   MqlDateTime t;
   t.year = year;  t.mon = mon;  t.day = day;
   t.hour = hour;  t.min = min;  t.sec = 0;
   t.day_of_week = 0;  t.day_of_year = 0;
   return(StructToTime(t));
  }

int DaysInMonth(const int year, const int mon)
  {
   int dim[12] = {31,28,31,30,31,30,31,31,30,31,30,31};
   if(mon == 2 && ((year%4 == 0 && year%100 != 0) || year%400 == 0))
      return(29);
   return(dim[mon-1]);
  }

//--- midnight of the nth Sunday of a month (nth = 1 for the first)
datetime NthSunday(const int year, const int mon, const int nth)
  {
   datetime first = MakeStamp(year, mon, 1, 0, 0);
   MqlDateTime t;
   TimeToStruct(first, t);
   int daysToSunday = (7 - t.day_of_week) % 7;   // day_of_week: 0 = Sunday
   return(first + (daysToSunday + 7*(nth-1)) * 86400);
  }

//--- midnight of the last Sunday of a month
datetime LastSunday(const int year, const int mon)
  {
   datetime last = MakeStamp(year, mon, DaysInMonth(year, mon), 0, 0);
   MqlDateTime t;
   TimeToStruct(last, t);
   return(last - t.day_of_week * 86400);
  }

//--- EU summer time: last Sunday of March 01:00 UTC to last Sunday of October 01:00 UTC
bool IsEuDst(const datetime utc)
  {
   MqlDateTime t;
   TimeToStruct(utc, t);
   datetime from = LastSunday(t.year, 3)  + 3600;
   datetime to   = LastSunday(t.year, 10) + 3600;
   return(utc >= from && utc < to);
  }

//--- US summer time: 2nd Sunday of March 02:00 EST (07:00 UTC)
//                 to 1st Sunday of November 02:00 EDT (06:00 UTC)
bool IsUsDst(const datetime utc)
  {
   MqlDateTime t;
   TimeToStruct(utc, t);
   datetime from = NthSunday(t.year, 3, 2)  + 7*3600;
   datetime to   = NthSunday(t.year, 11, 1) + 6*3600;
   return(utc >= from && utc < to);
  }

bool DstActive(const ENUM_DST_RULE rule, const datetime utc)
  {
   if(rule == DST_US) return(IsUsDst(utc));
   if(rule == DST_EU) return(IsEuDst(utc));
   return(false);
  }

//--- broker server offset from UTC, for a given UTC instant
int BrokerOffsetAtUtc(const datetime utc)
  {
   int off = g_brokerWinterOffsetSec;
   if(DstActive(InpBrokerDSTRule, utc))
      off += 3600;
   return(off);
  }

datetime UtcToBroker(const datetime utc)
  {
   return(utc + BrokerOffsetAtUtc(utc));
  }

//--- broker -> UTC. Two passes: guess with the winter offset, then refine.
datetime BrokerToUtc(const datetime brokerTime)
  {
   datetime guess = brokerTime - g_brokerWinterOffsetSec;
   int off = BrokerOffsetAtUtc(guess);
   datetime utc = brokerTime - off;
   off = BrokerOffsetAtUtc(utc);
   return(brokerTime - off);
  }

//--- offset of a session timezone from UTC, at a given UTC instant
int TzOffsetAtUtc(const ENUM_TZ tz, const datetime utc)
  {
   switch(tz)
     {
      case TZ_UTC:     return(0);
      case TZ_LONDON:  return(IsEuDst(utc) ? 3600 : 0);
      case TZ_NEWYORK: return(IsUsDst(utc) ? -4*3600 : -5*3600);
      case TZ_TOKYO:   return(9*3600);
      case TZ_BROKER:  return(BrokerOffsetAtUtc(utc));
     }
   return(0);
  }

//--- UTC instant -> naive wall-clock stamp in a session timezone
datetime UtcToLocal(const ENUM_TZ tz, const datetime utc)
  {
   return(utc + TzOffsetAtUtc(tz, utc));
  }

//--- naive wall-clock stamp in a session timezone -> UTC instant.
//--- Two passes, same reasoning as BrokerToUtc.
datetime LocalToUtc(const ENUM_TZ tz, const datetime local)
  {
   datetime utc = local - TzOffsetAtUtc(tz, local);
   return(local - TzOffsetAtUtc(tz, utc));
  }

datetime LocalToBroker(const ENUM_TZ tz, const datetime local)
  {
   return(UtcToBroker(LocalToUtc(tz, local)));
  }

//--- broker-time stamp of a wall-clock time-of-day, on the session-local day
//--- that contains 'nowBroker', stepping back until it is in the past.
datetime ResolvePastLocalTime(const datetime nowBroker, const ENUM_TZ tz,
                              const int hour, const int minute,
                              const int minSecondsInPast)
  {
   datetime nowUtc   = BrokerToUtc(nowBroker);
   datetime nowLocal = UtcToLocal(tz, nowUtc);
   MqlDateTime t;
   TimeToStruct(nowLocal, t);
   datetime candidate = MakeStamp(t.year, t.mon, t.day, hour, minute);

   for(int guard = 0; guard < 8; guard++)
     {
      if(candidate + minSecondsInPast <= nowLocal)
         break;
      candidate -= 86400;
     }
   return(LocalToBroker(tz, candidate));
  }

//--- broker-time window of the most recently COMPLETED session instance
void ResolveCompletedSession(const datetime nowBroker, const ENUM_TZ tz,
                             const int startHour, const int startMin,
                             const int endHour,   const int endMin,
                             datetime &startBroker, datetime &endBroker)
  {
   int startMinutes = startHour*60 + startMin;
   int endMinutes   = endHour*60   + endMin;
   int lengthMin    = (endMinutes > startMinutes)
                      ? (endMinutes - startMinutes)
                      : (endMinutes + 1440 - startMinutes);

   datetime nowUtc   = BrokerToUtc(nowBroker);
   datetime nowLocal = UtcToLocal(tz, nowUtc);
   MqlDateTime t;
   TimeToStruct(nowLocal, t);

   datetime endLocal = MakeStamp(t.year, t.mon, t.day, endHour, endMin);
   for(int guard = 0; guard < 8; guard++)
     {
      if(endLocal <= nowLocal)
         break;
      endLocal -= 86400;
     }
   datetime startLocal = endLocal - lengthMin*60;

   startBroker = LocalToBroker(tz, startLocal);
   endBroker   = LocalToBroker(tz, endLocal);
  }

//--- hard-exit wall-clock time for a given session-local day. Friday can
//--- differ, so the weekday of the day being asked about decides.
void HardExitTimeOfDay(const datetime localDay, int &hour, int &minute)
  {
   hour   = InpNYCloseHour;
   minute = InpNYCloseMin;
   if(!InpFridayEarlyClose)
      return;

   MqlDateTime t;
   TimeToStruct(localDay, t);
   if(t.day_of_week == 5)
     {
      hour   = InpFridayCloseHour;
      minute = InpFridayCloseMin;
     }
  }

//--- the next hard exit at or after 'nowBroker' (used for the panel and for
//--- the "no new entries near the close" filter)
datetime NextHardExit(const datetime nowBroker)
  {
   datetime nowLocal = UtcToLocal(InpNYCloseTZ, BrokerToUtc(nowBroker));
   MqlDateTime t;
   TimeToStruct(nowLocal, t);
   datetime dayLocal = MakeStamp(t.year, t.mon, t.day, 0, 0);

   for(int step = 0; step < 8; step++)
     {
      int hour, minute;
      HardExitTimeOfDay(dayLocal, hour, minute);
      datetime closeLocal = dayLocal + (hour*60 + minute)*60;
      if(closeLocal > nowLocal)
         return(LocalToBroker(InpNYCloseTZ, closeLocal));
      dayLocal += 86400;
     }
   return(nowBroker + 86400);
  }

//--- the most recent hard exit at or before 'nowBroker'. A position opened
//--- before this instant has outlived its session and must be flat - this is
//--- what makes the hard stop survive a terminal or VPS restart.
datetime PrevHardExit(const datetime nowBroker)
  {
   datetime nowLocal = UtcToLocal(InpNYCloseTZ, BrokerToUtc(nowBroker));
   MqlDateTime t;
   TimeToStruct(nowLocal, t);
   datetime dayLocal = MakeStamp(t.year, t.mon, t.day, 0, 0);

   for(int step = 0; step < 8; step++)
     {
      int hour, minute;
      HardExitTimeOfDay(dayLocal, hour, minute);
      datetime closeLocal = dayLocal + (hour*60 + minute)*60;
      if(closeLocal <= nowLocal)
         return(LocalToBroker(InpNYCloseTZ, closeLocal));
      dayLocal -= 86400;
     }
   return(nowBroker - 86400);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  HISTORY HELPERS                                                 |
//|                                                                  |
//+------------------------------------------------------------------+

//--- the 5-day ATR as it would have read on a given day, using only daily
//--- bars that had already closed by then
double ATRAsOf(const datetime whenBroker)
  {
   int firstShift = iBarShift(NULL, PERIOD_D1, whenBroker, false);
   if(firstShift < 0)
      return(0.0);

   int wanted = MathMax(1, InpATRDays);
   int collected = 0;
   double sum = 0.0;

   //--- firstShift is the day CONTAINING whenBroker, so start one bar back
   for(int step = 1; step <= wanted*4 + 10 && collected < wanted; step++)
     {
      int shift = firstShift + step;
      datetime barTime = iTime(NULL, PERIOD_D1, shift);
      if(barTime == 0)
         break;

      if(InpATRSkipSunday)
        {
         MqlDateTime t;
         TimeToStruct(barTime, t);
         if(t.day_of_week == 0)
            continue;
        }

      double high  = iHigh(NULL, PERIOD_D1, shift);
      double low   = iLow(NULL, PERIOD_D1, shift);
      double prevC = iClose(NULL, PERIOD_D1, shift+1);

      double trueRange = high - low;
      if(prevC > 0.0)
        {
         trueRange = MathMax(trueRange, MathAbs(high - prevC));
         trueRange = MathMax(trueRange, MathAbs(prevC - low));
        }
      sum += trueRange;
      collected++;
     }

   if(collected == 0)
      return(0.0);
   return(sum / collected);
  }

//--- highest high / lowest low of the bars fully inside a broker-time window
bool RangeInWindow(const ENUM_TIMEFRAMES tf,
                   const datetime startBroker, const datetime endBroker,
                   double &high, double &low)
  {
   int barSeconds = PeriodSeconds(tf);
   if(barSeconds <= 0)
      return(false);

   high = -DBL_MAX;
   low  =  DBL_MAX;
   bool found = false;

   int shift = iBarShift(NULL, tf, endBroker - 1, false);
   if(shift < 0)
      return(false);

   int maxBars = (int)((endBroker - startBroker) / barSeconds) + 4;
   for(int i = 0; i < maxBars; i++)
     {
      int s = shift + i;
      datetime barOpen = iTime(NULL, tf, s);
      if(barOpen == 0)
         break;
      if(barOpen < startBroker)
         break;
      if(barOpen + barSeconds <= endBroker)
        {
         high = MathMax(high, iHigh(NULL, tf, s));
         low  = MathMin(low,  iLow(NULL, tf, s));
         found = true;
        }
     }
   return(found && high > low);
  }

bool WeekdayAllowedAt(const datetime brokerTime)
  {
   MqlDateTime t;
   TimeToStruct(brokerTime, t);
   switch(t.day_of_week)
     {
      case 1: return(InpTradeMon);
      case 2: return(InpTradeTue);
      case 3: return(InpTradeWed);
      case 4: return(InpTradeThu);
      case 5: return(InpTradeFri);
     }
   return(false);
  }

bool SlotEnabled(const int slot)
  {
   if(InpMode == MODE_BOTH)
      return(true);
   if(slot == SLOT_ASIA)
      return(InpMode == MODE_ASIA_RANGE);
   return(InpMode == MODE_TRIGGER_CANDLE);
  }

string SlotName(const int slot)
  {
   return(slot == SLOT_ASIA ? "ASIA" : "CANDLE");
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  DRAWING                                                         |
//|                                                                  |
//+------------------------------------------------------------------+
//--- MT4 gets sluggish long before it complains, so cap the drawing rather
//--- than let a large InpDaysToShow quietly freeze the chart
#define MAX_OBJECTS 8000

bool RoomToDraw()
  {
   return(g_objCount < MAX_OBJECTS);
  }

string NextName(const string role)
  {
   return(StringFormat("%s%s_%d", OBJ_PREFIX, role, g_objCount++));
  }

void PaintBox(const datetime t1, const double p1, const datetime t2,
              const double p2, const color clr)
  {
   if(!RoomToDraw())
      return;
   string id = NextName("box");
   if(!ObjectCreate(0, id, OBJ_RECTANGLE, 0, t1, p1, t2, p2))
      return;
   ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, id, OBJPROP_BACK, true);
   ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
  }

void PaintSegment(const datetime t1, const double p1, const datetime t2,
                  const double p2, const color clr, const int style,
                  const int width)
  {
   if(!RoomToDraw())
      return;
   string id = NextName("seg");
   if(!ObjectCreate(0, id, OBJ_TREND, 0, t1, p1, t2, p2))
      return;
   ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, id, OBJPROP_STYLE, style);
   ObjectSetInteger(0, id, OBJPROP_WIDTH, width);
   ObjectSetInteger(0, id, OBJPROP_RAY_RIGHT, false);
   ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
  }

void PaintArrow(const datetime when, const double price, const int code,
                const color clr, const string tip)
  {
   if(!RoomToDraw())
      return;
   string id = NextName("arw");
   if(!ObjectCreate(0, id, OBJ_ARROW, 0, when, price))
      return;
   ObjectSetInteger(0, id, OBJPROP_ARROWCODE, code);
   ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, id, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
   ObjectSetString(0, id, OBJPROP_TEXT, tip);
  }

void PaintText(const datetime when, const double price, const string text,
               const color clr)
  {
   if(!RoomToDraw())
      return;
   string id = NextName("txt");
   if(!ObjectCreate(0, id, OBJ_TEXT, 0, when, price))
      return;
   ObjectSetString(0, id, OBJPROP_TEXT, text);
   ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, id, OBJPROP_FONTSIZE, 7);
   ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
  }

void ClearObjects()
  {
   long chart = ChartID();
   for(int i = ObjectsTotal(chart, -1, -1) - 1; i >= 0; i--)
     {
      string name = ObjectName(chart, i, -1, -1);
      if(StringFind(name, OBJ_PREFIX) == 0)
         ObjectDelete(chart, name);
     }
   g_objCount = 0;
  }


//+------------------------------------------------------------------+
//| CSV export                                                       |
//+------------------------------------------------------------------+
void OpenCSV()
  {
   if(!InpExportCSV)
      return;
   string file = StringFormat("%s_replay_%s_%s.csv", InpTag, Symbol(),
                              TimeToString(TimeCurrent(), TIME_DATE));
   g_csvHandle = FileOpen(file, FILE_CSV|FILE_WRITE|FILE_SHARE_READ, ',');
   if(g_csvHandle == INVALID_HANDLE)
     {
      PrintFormat("[%s] could not open %s for writing (error %d)",
                  InpTag, file, GetLastError());
      return;
     }
   FileWrite(g_csvHandle, "day", "slot", "dir", "level_high", "level_low",
             "atr5", "entry_time", "entry", "stop_level", "target",
             "partial_taken", "exit_time", "exit", "reason", "r_multiple", "pips");
  }

void CloseCSV()
  {
   if(g_csvHandle != INVALID_HANDLE)
     {
      FileClose(g_csvHandle);
      g_csvHandle = INVALID_HANDLE;
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  HISTORY DEPTH                                                   |
//|                                                                  |
//|  The replay reads three or four timeframes, and MT4 loads them    |
//|  lazily. Summing their bar counts gives a cheap fingerprint: when |
//|  it grows, more history has arrived and the replay is worth       |
//|  rebuilding. This is what stops the picture freezing at whatever  |
//|  happened to be in memory when the indicator was attached.        |
//+------------------------------------------------------------------+
int HistoryFingerprint()
  {
   int total = iBars(NULL, InpEntryTF) + iBars(NULL, InpEntryTF)
             + iBars(NULL, PERIOD_D1);
   if(InpMode != MODE_ASIA_RANGE)
      total += iBars(NULL, InpTriggerTF);
   return(total);
  }

string DescribeTF(const string label, const ENUM_TIMEFRAMES tf, const int needed)
  {
   int bars = iBars(NULL, tf);
   datetime oldest = (bars > 0) ? iTime(NULL, tf, bars - 1) : 0;
   string verdict = (bars >= needed) ? "ok" : "SHORT";
   return(StringFormat("  %-8s %-5s %6d bars  back to %s  [%s]\n",
                       label, StringSubstr(EnumToString(tf), 7), bars,
                       (oldest > 0 ? TimeToString(oldest, TIME_DATE) : "-"),
                       verdict));
  }

//--- what the requested replay depth actually needs, per timeframe
void BuildHistoryReport()
  {
   int signalMin = PeriodSeconds(InpEntryTF) / 60;
   int rangeMin  = PeriodSeconds(InpEntryTF) / 60;
   int needSignal = (signalMin > 0) ? InpDaysToShow * (1440 / MathMax(1, signalMin)) : 0;
   int needRange  = (rangeMin  > 0) ? InpDaysToShow * (1440 / MathMax(1, rangeMin))  : 0;
   int needDaily  = InpDaysToShow + InpATRDays + 10;

   g_historyReport  = DescribeTF("signal", InpEntryTF, needSignal);
   g_historyReport += DescribeTF("range",  InpEntryTF,  needRange);
   g_historyReport += DescribeTF("daily",  PERIOD_D1,   needDaily);
   if(InpMode != MODE_ASIA_RANGE)
      g_historyReport += DescribeTF("trigger", InpTriggerTF, InpDaysToShow);
  }

//+------------------------------------------------------------------+
//| Record and draw one finished trade                               |
//+------------------------------------------------------------------+
void FinishTrade(const int slot, const int dir, const int reason,
                 const double entry, const double stop, const double tp,
                 const datetime entryTime, const datetime exitTime,
                 const double exitPrice, const bool partialTaken,
                 const datetime partialTime, const datetime dayStamp,
                 const double levelHigh, const double levelLow,
                 const double atr5)
  {
   double risk = MathAbs(entry - stop);
   if(risk <= 0.0)
      return;

   double rTarget = ((dir == DIR_LONG) ? (tp - entry) : (entry - tp)) / risk;
   double rRest   = ((dir == DIR_LONG) ? (exitPrice - entry) : (entry - exitPrice)) / risk;

   //--- the blended result: the slice taken at the target plus the runner
   double fraction = (partialTaken && InpPartialClosePct > 0.0 && InpPartialClosePct < 100.0)
                     ? InpPartialClosePct / 100.0 : 0.0;
   double r = fraction * rTarget + (1.0 - fraction) * rRest;

   //--- the same blend in pips: the slice banked at the target plus the
   //--- runner, weighted by how much of the position each carried
   double pipsTarget = ((dir == DIR_LONG) ? (tp - entry) : (entry - tp)) / g_pipSize;
   double pipsRest   = ((dir == DIR_LONG) ? (exitPrice - entry) : (entry - exitPrice)) / g_pipSize;
   double pips = fraction * pipsTarget + (1.0 - fraction) * pipsRest;

   bool touchedTarget = partialTaken || (reason == EXIT_TARGET);

   g_nTrades[slot]++;
   g_sumR[slot] += r;
   if(g_nTrades[slot] == 1) { g_bestR[slot] = r; g_worstR[slot] = r; }
   g_bestR[slot]  = MathMax(g_bestR[slot], r);
   g_worstR[slot] = MathMin(g_worstR[slot], r);

   g_sumPips[slot] += pips;
   if(pips >= 0.0) g_wonPips[slot]  += pips;
   else            g_lostPips[slot] += pips;
   if(g_nTrades[slot] == 1) { g_bestPips[slot] = pips; g_worstPips[slot] = pips; }
   g_bestPips[slot]  = MathMax(g_bestPips[slot], pips);
   g_worstPips[slot] = MathMin(g_worstPips[slot], pips);

   if(touchedTarget)          g_nWins[slot]++;
   if(partialTaken)           g_nPartials[slot]++;
   if(reason == EXIT_STOP)    g_nLosses[slot]++;
   if(reason == EXIT_NYCLOSE) g_nFlat[slot]++;
   if(reason == EXIT_REVERSE) g_nReverse[slot]++;

   color finalClr = (reason == EXIT_TARGET)  ? InpColorWin
                  : (reason == EXIT_STOP)    ? InpColorLoss
                  : (reason == EXIT_REVERSE) ? InpColorReverse
                                             : InpColorFlat;
   string reasonText = (reason == EXIT_TARGET)  ? "TP"
                     : (reason == EXIT_STOP)    ? "SL"
                     : (reason == EXIT_REVERSE) ? "RV"
                                                : "NY";

   PaintArrow(entryTime, entry, (dir == DIR_LONG) ? 233 : 234, finalClr,
              StringFormat("%s %s entry %s", SlotName(slot), DirName(dir),
                           DoubleToString(entry, Digits)));

   if(partialTaken)
     {
      //--- two legs: entry to the point the slice was taken, then the runner
      PaintSegment(entryTime, entry, partialTime, tp, InpColorWin, STYLE_SOLID, 2);
      PaintArrow(partialTime, tp, 159, InpColorWin,
                 StringFormat("%.0f%% taken at target %s", InpPartialClosePct,
                              DoubleToString(tp, Digits)));
      PaintSegment(partialTime, tp, exitTime, exitPrice, finalClr, STYLE_SOLID, 2);
     }
   else
     {
      PaintSegment(entryTime, entry, exitTime, exitPrice, finalClr, STYLE_SOLID, 2);
     }

   if(InpShowLevels)
     {
      PaintSegment(entryTime, tp,   exitTime, tp,   InpColorWin,  STYLE_DOT, 1);
      PaintSegment(entryTime, stop, exitTime, stop, InpColorLoss, STYLE_DOT, 1);
     }

   if(InpShowLabels)
      PaintText(exitTime, exitPrice,
                StringFormat(" %s%s %+.2fR", reasonText,
                             (partialTaken ? "*" : ""), r), finalClr);

   if(g_csvHandle != INVALID_HANDLE)
      FileWrite(g_csvHandle,
                TimeToString(dayStamp, TIME_DATE),
                SlotName(slot), DirName(dir),
                DoubleToString(levelHigh, Digits),
                DoubleToString(levelLow, Digits),
                DoubleToString(atr5, Digits),
                TimeToString(entryTime, TIME_DATE|TIME_MINUTES),
                DoubleToString(entry, Digits),
                DoubleToString(stop, Digits),
                DoubleToString(tp, Digits),
                (partialTaken ? "yes" : "no"),
                TimeToString(exitTime, TIME_DATE|TIME_MINUTES),
                DoubleToString(exitPrice, Digits),
                reasonText,
                DoubleToString(r, 3),
                DoubleToString(pips, 1));
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  THE REPLAY                                                      |
//|                                                                  |
//|  One trading day, one flavor, simulated bar by bar. A long and a  |
//|  short can be live at the same time, each with its own stop,      |
//|  target and partial-fill state, exactly as EA v2 runs them.       |
//+------------------------------------------------------------------+
int DirIndex(const int dir) { return(dir == DIR_LONG ? DX_LONG : DX_SHORT); }
int DirOf(const int dx)     { return(dx == DX_LONG ? DIR_LONG : DIR_SHORT); }
string DirName(const int dir) { return(dir == DIR_LONG ? "LONG" : "SHORT"); }

int ReplayDay(const datetime nyClose, const int slot)
  {
   int period = PeriodSeconds(InpEntryTF);
   if(period <= 0)
      return(0);

   //--- 1. the levels this day would have traded ------------------------
   double levelHigh = 0, levelLow = 0, stopHigh = 0, stopLow = 0;
   datetime levelReadyAt = 0, boxFrom = 0, boxTo = 0;

   datetime asiaStart = 0, asiaEnd = 0;
   double   asiaHigh = 0, asiaLow = 0;

   ResolveCompletedSession(nyClose, InpAsiaTZ,
                           InpAsiaStartHour, InpAsiaStartMin,
                           InpAsiaEndHour,   InpAsiaEndMin,
                           asiaStart, asiaEnd);
   bool asiaOk = RangeInWindow(InpEntryTF, asiaStart, asiaEnd, asiaHigh, asiaLow);

   if(slot == SLOT_ASIA)
     {
      if(!asiaOk)
        { g_nSkipNoData[slot]++; return(0); }
      levelHigh = asiaHigh;  levelLow = asiaLow;
      stopHigh  = asiaHigh;  stopLow  = asiaLow;
      levelReadyAt = asiaEnd;
      boxFrom = asiaStart;   boxTo = asiaEnd;
     }
   else
     {
      int trigPeriod = PeriodSeconds(InpTriggerTF);
      datetime trigOpen = ResolvePastLocalTime(nyClose, InpTriggerTZ,
                                               InpTriggerHour, InpTriggerMin,
                                               trigPeriod);
      int trigShift = iBarShift(NULL, InpTriggerTF, trigOpen, true);
      if(trigShift < 0)
        { g_nSkipNoData[slot]++; return(0); }

      levelHigh = iHigh(NULL, InpTriggerTF, trigShift);
      levelLow  = iLow(NULL, InpTriggerTF, trigShift);
      if(levelHigh <= levelLow)
        { g_nSkipNoData[slot]++; return(0); }

      if(InpCandleSLSource == CSL_ASIA_SESSION)
        {
         if(!asiaOk)
           { g_nSkipNoData[slot]++; return(0); }
         stopHigh = asiaHigh;  stopLow = asiaLow;
        }
      else
        {
         stopHigh = levelHigh;  stopLow = levelLow;
        }
      levelReadyAt = trigOpen + trigPeriod;
      boxFrom = trigOpen;  boxTo = levelReadyAt;
     }

   if(levelReadyAt <= PrevHardExit(nyClose - 60) || levelReadyAt >= nyClose)
     { g_nSkipNoData[slot]++; return(0); }

   if(!WeekdayAllowedAt(levelReadyAt))
     { g_nSkipFilter[slot]++; return(0); }

   g_nDays[slot]++;

   bool wantBox = (slot == SLOT_ASIA) ? InpShowAsiaBox : InpShowTriggerBox;
   if(wantBox)
      PaintBox(boxFrom, levelHigh, boxTo, levelLow,
               (slot == SLOT_ASIA) ? InpColorAsia : InpColorTrigger);

   double atr5 = ATRAsOf(levelReadyAt);
   if(atr5 <= 0.0)
     { g_nSkipNoData[slot]++; return(0); }

   double rangePoints = (levelHigh - levelLow) / g_pointsToPrice;
   if((InpMinRangePoints > 0 && rangePoints < InpMinRangePoints) ||
      (InpMaxRangePoints > 0 && rangePoints > InpMaxRangePoints))
     {
      g_nSkipFilter[slot]++;
      if(InpShowSkips)
         PaintText(levelReadyAt, levelHigh, " range filter", InpColorSkip);
      return(0);
     }

   //--- the range price broke out of, and which the reversal exit measures
   //--- against: the Asia range in Asia mode, the trigger candle in candle mode
   double rangeHeight = levelHigh - levelLow;

   double targetDist = InpTPPctOfATR / 100.0 * atr5;
   double buffer     = InpBreakoutBufferPoints * g_pointsToPrice;

   int startShift = iBarShift(NULL, InpEntryTF, levelReadyAt, false);
   int endShift   = iBarShift(NULL, InpEntryTF, nyClose - 1, false);

   //--- shift 0 is the bar still forming. Replaying the day in progress must
   //--- stop at the last CLOSED bar or the drawing would change under itself,
   //--- which is exactly the repainting this indicator promises not to do.
   if(endShift < 1)
      endShift = 1;

   if(startShift < 0 || endShift < 0 || startShift < endShift)
     { g_nSkipNoData[slot]++; return(0); }

   //--- 2. simulation state, one slot per direction ----------------------
   bool     live[DX_COUNT];
   int      entryShiftOf[DX_COUNT];
   double   entryOf[DX_COUNT], stopOf[DX_COUNT], tpOf[DX_COUNT];
   datetime entryTimeOf[DX_COUNT];
   bool     partialOf[DX_COUNT];
   datetime partialTimeOf[DX_COUNT];
   bool     armed[DX_COUNT];
   double   bestOf[DX_COUNT];

   for(int dx = 0; dx < DX_COUNT; dx++)
     {
      live[dx] = false;  partialOf[dx] = false;  armed[dx] = true;  bestOf[dx] = 0;
      entryShiftOf[dx] = 0;  entryOf[dx] = 0;  stopOf[dx] = 0;  tpOf[dx] = 0;
      entryTimeOf[dx] = 0;   partialTimeOf[dx] = 0;
     }

   int  taken   = 0;
   bool sawBar  = false;
   bool skipped = false;

   //--- 3. walk the day ---------------------------------------------------
   for(int k = startShift; k >= endShift; k--)
     {
      datetime barOpen  = iTime(NULL, InpEntryTF, k);
      datetime barClose = barOpen + period;
      if(barClose <= levelReadyAt) continue;
      if(barOpen  >= nyClose)      break;
      sawBar = true;

      double hi = iHigh(NULL, InpEntryTF, k);
      double lo = iLow(NULL, InpEntryTF, k);
      double cl = iClose(NULL, InpEntryTF, k);

      //--- 3a. manage what is already open on this bar
      for(int dx = 0; dx < DX_COUNT; dx++)
        {
         if(!live[dx])            continue;
         if(k > entryShiftOf[dx]) continue;   // not open yet on this bar

         int dir = DirOf(dx);

         //--- TARGET FIRST, and not as a tie-break: it is a resting order
         //--- that fills the moment price trades there, while the stop is
         //--- not even looked at until the bar has closed.
         //--- the high-water mark this bar, before anything is tested against
         //--- it, so a bar that runs up and reverses can trigger a giveback
         //--- within itself - which is what actually happens
         if(bestOf[dx] <= 0.0)
            bestOf[dx] = entryOf[dx];
         bestOf[dx] = (dir == DIR_LONG) ? MathMax(bestOf[dx], hi)
                                        : MathMin(bestOf[dx], lo);

         double revLevel = 0.0;
         if(InpUseReversalExit && InpReversalPctOfRange > 0.0 && rangeHeight > 0.0)
           {
            double give = rangeHeight * InpReversalPctOfRange / 100.0;
            double from = 0.0;
            if(InpReversalFrom == REV_FROM_PEAK)       from = bestOf[dx];
            else if(InpReversalFrom == REV_FROM_ENTRY) from = entryOf[dx];
            else                                       from = (dir == DIR_LONG) ? levelHigh : levelLow;
            revLevel = (dir == DIR_LONG) ? from - give : from + give;
           }

         bool revHit = false;
         double revFill = 0.0;
         if(revLevel > 0.0)
           {
            if(InpStopStyle == STOP_ON_TOUCH)
              {
               revHit  = (dir == DIR_LONG) ? (lo <= revLevel) : (hi >= revLevel);
               revFill = revLevel;
              }
            else
              {
               revHit  = (dir == DIR_LONG) ? (cl <= revLevel) : (cl >= revLevel);
               revFill = cl;
              }
           }

         //--- with a TOUCH stop both levels can be reached inside one bar and
         //--- the bar does not say which came first. Assume the stop, so the
         //--- replay never flatters the strategy.
         bool stopAlsoHit = ((InpStopStyle == STOP_ON_TOUCH) &&
                             ((dir == DIR_LONG) ? (lo <= stopOf[dx]) : (hi >= stopOf[dx])))
                            || (revHit && InpStopStyle == STOP_ON_TOUCH);

         if(!partialOf[dx] && !stopAlsoHit)
           {
            bool touched = (dir == DIR_LONG) ? (hi >= tpOf[dx]) : (lo <= tpOf[dx]);
            if(touched)
              {
               if(InpPartialClosePct >= 100.0)
                 {
                  FinishTrade(slot, dir, EXIT_TARGET, entryOf[dx], stopOf[dx],
                              tpOf[dx], entryTimeOf[dx], barClose, tpOf[dx],
                              false, 0, levelReadyAt, levelHigh, levelLow, atr5);
                  live[dx] = false;
                  continue;
                 }
               if(InpPartialClosePct > 0.0)
                 {
                  partialOf[dx]     = true;
                  partialTimeOf[dx] = barClose;
                  if(InpMoveStopAfterPartial)
                     stopOf[dx] = entryOf[dx];
                 }
              }
           }

         //--- the reversal exit is offered the bar before the structural stop,
         //--- since it is usually the tighter of the two
         if(revHit)
           {
            FinishTrade(slot, dir, EXIT_REVERSE, entryOf[dx], stopOf[dx], tpOf[dx],
                        entryTimeOf[dx], barClose, revFill, partialOf[dx],
                        partialTimeOf[dx], levelReadyAt, levelHigh, levelLow, atr5);
            live[dx] = false;
            continue;
           }

         //--- the structural stop, in whichever style is configured
         bool   stopped   = false;
         double stopFill  = cl;
         if(InpStopStyle == STOP_ON_TOUCH)
           {
            //--- a resting stop fills the moment price reaches it, at the level
            stopped  = (dir == DIR_LONG) ? (lo <= stopOf[dx]) : (hi >= stopOf[dx]);
            stopFill = stopOf[dx];
           }
         else
           {
            stopped  = (dir == DIR_LONG) ? (cl < stopOf[dx]) : (cl > stopOf[dx]);
            stopFill = cl;
           }

         if(stopped)
           {
            FinishTrade(slot, dir, EXIT_STOP, entryOf[dx], stopOf[dx], tpOf[dx],
                        entryTimeOf[dx], barClose, stopFill, partialOf[dx],
                        partialTimeOf[dx], levelReadyAt, levelHigh, levelLow, atr5);
            live[dx] = false;
           }
        }

      //--- 3b. re-arming, only when the option is on
      if(InpRequireReset)
         for(int dx = 0; dx < DX_COUNT; dx++)
           {
            if(armed[dx] || live[dx]) continue;
            bool backInside = (DirOf(dx) == DIR_LONG) ? (cl <= levelHigh) : (cl >= levelLow);
            if(backInside)
               armed[dx] = true;
           }

      //--- 3c. a new entry from this bar's close
      if(taken >= InpMaxTradesPerDay)                       continue;
      if(barClose + InpNoNewTradesBeforeCloseM*60 >= nyClose) continue;

      int dir = DIR_NONE;
      if(cl > levelHigh + buffer)      dir = DIR_LONG;
      else if(cl < levelLow - buffer)  dir = DIR_SHORT;
      if(dir == DIR_NONE) continue;

      int dxNew = DirIndex(dir);
      if(live[dxNew])   continue;          // one open per direction
      if(!armed[dxNew]) continue;
      if((dir == DIR_LONG && !InpTradeLongs) || (dir == DIR_SHORT && !InpTradeShorts))
         continue;

      int entryShift = k - 1;
      if(entryShift < endShift) continue;  // no bar left in the day to open on

      double entry = iOpen(NULL, InpEntryTF, entryShift);
      double structural = (dir == DIR_LONG) ? stopLow : stopHigh;
      double tp         = (dir == DIR_LONG) ? stopLow + targetDist
                                            : stopHigh - targetDist;

      if(InpMaxSLPoints > 0 &&
         MathAbs(entry - structural) / g_pointsToPrice > InpMaxSLPoints)
        { g_nSkipFilter[slot]++; skipped = true; continue; }

      bool targetBehind = (dir == DIR_LONG) ? (tp <= entry) : (tp >= entry);
      if(targetBehind)
        {
         g_nSkipTarget[slot]++;
         skipped = true;
         if(InpShowSkips)
            PaintText(iTime(NULL, InpEntryTF, entryShift),
                      (dir == DIR_LONG) ? levelHigh : levelLow,
                      " target behind entry", InpColorSkip);
         continue;
        }

      live[dxNew]         = true;
      armed[dxNew]        = false;
      partialOf[dxNew]    = false;
      entryShiftOf[dxNew] = entryShift;
      entryTimeOf[dxNew]  = iTime(NULL, InpEntryTF, entryShift);
      entryOf[dxNew]      = entry;
      bestOf[dxNew]       = entry;
      stopOf[dxNew]       = structural;
      tpOf[dxNew]         = tp;
      taken++;
     }

   //--- 4. the hard exit: whatever is still open goes at the NY close ------
   double lastClose = iClose(NULL, InpEntryTF, endShift);
   datetime lastTime = iTime(NULL, InpEntryTF, endShift) + period;
   for(int dx = 0; dx < DX_COUNT; dx++)
      if(live[dx])
        {
         FinishTrade(slot, DirOf(dx), EXIT_NYCLOSE, entryOf[dx], stopOf[dx],
                     tpOf[dx], entryTimeOf[dx], lastTime, lastClose,
                     partialOf[dx], partialTimeOf[dx], levelReadyAt,
                     levelHigh, levelLow, atr5);
         live[dx] = false;
        }

   if(taken == 0 && sawBar && !skipped)
     {
      g_nSkipNoBreak[slot]++;
      if(InpShowSkips)
         PaintText(levelReadyAt, levelLow, " no breakout", InpColorSkip);
     }

   return(taken);
  }

//+------------------------------------------------------------------+
//| Summary panel                                                    |
//+------------------------------------------------------------------+
void ShowSummary(const int daysWalked)
  {
   if(!InpShowPanel)
     {
      PanelClear();
      return;
     }

   string exitPlan = (InpPartialClosePct <= 0.0)
                     ? "no target, all to NY close"
                     : (InpPartialClosePct >= 100.0
                        ? "100% at target"
                        : StringFormat("%.0f%% at target, %.0f%% to NY close",
                                       InpPartialClosePct, 100.0 - InpPartialClosePct));

   string text = StringFormat("%s replay v2  %s   %d trading days\n",
                              InpTag, Symbol(), daysWalked);
   text += StringFormat("TF  %s breaks the range%s\n",
                        StringSubstr(EnumToString(InpEntryTF), 7),
                        (InpMode == MODE_ASIA_RANGE ? "" :
                         StringFormat("  |  trigger candle %s",
                                      StringSubstr(EnumToString(InpTriggerTF), 7))));
   text += StringFormat("Target %.0f%% of ATR%d from the level | exit: %s\n",
                        InpTPPctOfATR, InpATRDays, exitPlan);
   if(InpUseReversalExit)
      text += StringFormat("Reversal exit: %.0f%% of the range back from %s\n",
                           InpReversalPctOfRange,
                           (InpReversalFrom == REV_FROM_PEAK  ? "the best price" :
                            InpReversalFrom == REV_FROM_ENTRY ? "entry" :
                                                                "the level it broke"));
   text += StringFormat("Structural stop: %s\n",
                        (InpStopStyle == STOP_ON_TOUCH
                         ? "ON TOUCH - fills the moment price reaches the level"
                         : "ON CLOSE - a bar must close beyond the level"));
   text += StringFormat("Up to %d entries/day, 1 open per direction\n\n",
                        InpMaxTradesPerDay);

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      if(!SlotEnabled(slot))
         continue;

      int n = g_nTrades[slot];
      text += StringFormat("%-7s %d trades over %d days\n",
                           SlotName(slot), n, g_nDays[slot]);

      if(n > 0)
        {
         text += StringFormat("        target reached %d (%.0f%%)   of which scaled out %d\n",
                              g_nWins[slot], 100.0 * g_nWins[slot] / n, g_nPartials[slot]);
         text += StringFormat("        ended: %d at target, %d on a stop, %d reversal, %d at the NY close\n",
                              n - g_nLosses[slot] - g_nFlat[slot] - g_nReverse[slot],
                              g_nLosses[slot], g_nReverse[slot], g_nFlat[slot]);
         text += StringFormat("        total %+.2fR   avg %+.2fR   best %+.2fR   worst %+.2fR\n",
                              g_sumR[slot], g_sumR[slot] / n, g_bestR[slot], g_worstR[slot]);
         text += StringFormat("        PIPS  %+.1f total   %+.1f avg   won %+.1f   lost %.1f\n",
                              g_sumPips[slot], g_sumPips[slot] / n,
                              g_wonPips[slot], g_lostPips[slot]);
         text += StringFormat("              best %+.1f   worst %+.1f\n",
                              g_bestPips[slot], g_worstPips[slot]);
        }

      int skipped = g_nSkipNoBreak[slot] + g_nSkipTarget[slot]
                  + g_nSkipFilter[slot] + g_nSkipNoData[slot];
      if(skipped > 0)
         text += StringFormat("        skipped: %d no breakout, %d target behind entry, "
                              "%d filtered, %d no data\n",
                              g_nSkipNoBreak[slot], g_nSkipTarget[slot],
                              g_nSkipFilter[slot], g_nSkipNoData[slot]);
      text += "\n";
     }

   text += "History available:\n" + g_historyReport;

   //--- if days were lost to missing bars, say so plainly rather than let it
   //--- look like the rules found nothing
   int noData = 0;
   for(int slot = 0; slot < SLOT_COUNT; slot++)
      if(SlotEnabled(slot))
         noData += g_nSkipNoData[slot];
   if(noData > 0)
      text += StringFormat("\n%d day(s) had no usable bars. If a timeframe above says "
                           "SHORT, that is the limit - open that timeframe's chart once, "
                           "or raise Tools > Options > Charts > Max bars in history.\n",
                           noData);

   text += "\nR is measured against the STRUCTURAL stop and blends the slice taken\n";
   text += "at the target with the runner. Spread, slippage and swap are not\n";
   text += "modelled, so live results will be slightly worse.\n";

   g_panelBlock = text;
   PanelRender(text);
  }

//+------------------------------------------------------------------+
//| Run the whole replay                                             |
//+------------------------------------------------------------------+
void Rebuild()
  {
   ClearObjects();
   CloseCSV();
   OpenCSV();
   BuildHistoryReport();

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      g_nTrades[slot] = 0;  g_nWins[slot]   = 0;  g_nLosses[slot] = 0;
      g_nFlat[slot]   = 0;  g_nPartials[slot] = 0;  g_nReverse[slot] = 0;
      g_sumR[slot]    = 0;  g_bestR[slot]   = 0;  g_worstR[slot]  = 0;
      g_sumPips[slot] = 0;  g_wonPips[slot] = 0;  g_lostPips[slot] = 0;
      g_bestPips[slot] = 0; g_worstPips[slot] = 0;
      g_nDays[slot]   = 0;
      g_nSkipNoBreak[slot] = 0;  g_nSkipTarget[slot] = 0;
      g_nSkipFilter[slot]  = 0;  g_nSkipNoData[slot] = 0;
     }

   int daysWalked = 0;

   //--- the day in progress, clipped to now rather than to its NY close
   if(InpIncludeToday)
     {
      datetime nextClose = NextHardExit(TimeCurrent());
      datetime cutoff    = (datetime)MathMin((double)nextClose, (double)TimeCurrent());
      for(int slot = 0; slot < SLOT_COUNT; slot++)
         if(SlotEnabled(slot))
            ReplayDay(cutoff, slot);
      daysWalked++;
     }

   datetime nyClose = PrevHardExit(TimeCurrent());
   for(int d = 0; d < InpDaysToShow; d++)
     {
      if(nyClose <= 0)
         break;
      for(int slot = 0; slot < SLOT_COUNT; slot++)
         if(SlotEnabled(slot))
            ReplayDay(nyClose, slot);
      daysWalked++;
      nyClose = PrevHardExit(nyClose - 60);
     }

   CloseCSV();
   ShowSummary(daysWalked);

   int drawn = 0;
   for(int slot = 0; slot < SLOT_COUNT; slot++)
      drawn += g_nTrades[slot];

   PrintFormat("[%s] replayed %d trading days, %d trades, %d objects.",
               InpTag, daysWalked, drawn, g_objCount);
   if(g_objCount >= MAX_OBJECTS)
      PrintFormat("[%s] hit the %d object cap - the oldest days are not drawn. "
                  "Lower InpDaysToShow or turn off some display options. The "
                  "panel totals still cover every day replayed.",
                  InpTag, MAX_OBJECTS);
  }


//+------------------------------------------------------------------+
//|                                                                  |
//|  PANEL                                                           |
//|                                                                  |
//|  Comment() writes at a fixed, small size that MT4 will not let    |
//|  you change, so the panel is drawn instead: a rectangle label as  |
//|  the background and one text label per line. That buys a chosen   |
//|  font and size, real colours, any corner of the chart, and a      |
//|  button to fold it away.                                         |
//|                                                                  |
//|  Use a MONOSPACED font (Consolas, Courier New) or the columns     |
//|  will not line up - MT4 gives no way to measure rendered text,    |
//|  so the box is sized from a per-character width estimate.         |
//+------------------------------------------------------------------+
#define PANEL_PREFIX "ABPNLI_"   // I = indicator; the EA uses ABPNLE_
#define PANEL_TOGGLE PANEL_PREFIX "toggle"

bool g_panelOpen = true;

bool PanelCornerIsLower()
  {
   return(InpPanelCorner == CORNER_LEFT_LOWER || InpPanelCorner == CORNER_RIGHT_LOWER);
  }

ENUM_ANCHOR_POINT PanelAnchor()
  {
   switch(InpPanelCorner)
     {
      case CORNER_RIGHT_UPPER: return(ANCHOR_RIGHT_UPPER);
      case CORNER_LEFT_LOWER:  return(ANCHOR_LEFT_LOWER);
      case CORNER_RIGHT_LOWER: return(ANCHOR_RIGHT_LOWER);
     }
   return(ANCHOR_LEFT_UPPER);
  }

void PanelClear()
  {
   long chart = ChartID();
   for(int i = ObjectsTotal(chart, -1, -1) - 1; i >= 0; i--)
     {
      string name = ObjectName(chart, i, -1, -1);
      if(StringFind(name, PANEL_PREFIX) == 0)
         ObjectDelete(chart, name);
     }
  }

void PanelDropLines()
  {
   long chart = ChartID();
   for(int i = ObjectsTotal(chart, -1, -1) - 1; i >= 0; i--)
     {
      string name = ObjectName(chart, i, -1, -1);
      if(StringFind(name, PANEL_PREFIX "L") == 0 || name == PANEL_PREFIX "bg")
         ObjectDelete(chart, name);
     }
  }

void PanelButton(const int x, const int y, const int w, const int h)
  {
   if(!InpPanelShowToggle)
      return;

   if(ObjectFind(0, PANEL_TOGGLE) < 0)
      ObjectCreate(0, PANEL_TOGGLE, OBJ_BUTTON, 0, 0, 0);

   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_CORNER,    InpPanelCorner);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_XSIZE,     w);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_YSIZE,     h);
   ObjectSetString (0, PANEL_TOGGLE, OBJPROP_TEXT,      g_panelOpen ? "HIDE STATS" : "SHOW STATS");
   ObjectSetString (0, PANEL_TOGGLE, OBJPROP_FONT,      InpPanelFont);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_FONTSIZE,  InpPanelFontSize);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_COLOR,     InpPanelTextColor);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_BGCOLOR,   InpPanelBgColor);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_BORDER_COLOR, InpPanelBorderColor);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_STATE,     false);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_HIDDEN,    true);
  }

void PanelLine(const int index, const int x, const int y, const string text)
  {
   string name = StringFormat("%sL%03d", PANEL_PREFIX, index);
   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);

   ObjectSetInteger(0, name, OBJPROP_CORNER,     InpPanelCorner);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR,     PanelAnchor());
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE,  x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE,  y);
   ObjectSetString (0, name, OBJPROP_TEXT,       (StringLen(text) > 0 ? text : " "));
   ObjectSetString (0, name, OBJPROP_FONT,       InpPanelFont);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE,   InpPanelFontSize);
   ObjectSetInteger(0, name, OBJPROP_COLOR,      InpPanelTextColor);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, name, OBJPROP_HIDDEN,     true);
  }

//--- render a whole block of text, newline separated
void PanelRender(const string block)
  {
   if(!InpShowPanel)
     {
      PanelClear();
      return;
     }

   int lineH = (int)MathRound(InpPanelFontSize * 1.75) + 2;
   int charW = (int)MathRound(InpPanelFontSize * 0.62) + 1;
   int padX  = 8;
   int padY  = 6;
   int btnH  = InpPanelShowToggle ? (lineH + 8) : 0;
   int btnW  = 11 * charW + 2 * padX;

   PanelButton(InpPanelX, InpPanelY, btnW, btnH);

   if(!g_panelOpen)
     {
      PanelDropLines();
      ChartRedraw();
      return;
     }

   string lines[];
   int count = StringSplit(block, '\n', lines);
   if(count <= 0)
     {
      PanelDropLines();
      return;
     }

   //--- MT4 cannot measure rendered text, so the width is estimated from the
   //--- longest line. A monospaced font makes the estimate accurate.
   int widest = 0;
   for(int i = 0; i < count; i++)
      widest = MathMax(widest, StringLen(lines[i]));

   int boxW = (InpPanelWidthChars > 0 ? InpPanelWidthChars : widest) * charW + 2 * padX;
   int boxH = count * lineH + 2 * padY;
   int top  = InpPanelY + btnH + (btnH > 0 ? 4 : 0);

   //--- background
   string bg = PANEL_PREFIX "bg";
   if(ObjectFind(0, bg) < 0)
      ObjectCreate(0, bg, OBJ_RECTANGLE_LABEL, 0, 0, 0);
   ObjectSetInteger(0, bg, OBJPROP_CORNER,       InpPanelCorner);
   ObjectSetInteger(0, bg, OBJPROP_XDISTANCE,    InpPanelX);
   ObjectSetInteger(0, bg, OBJPROP_YDISTANCE,    top);
   ObjectSetInteger(0, bg, OBJPROP_XSIZE,        boxW);
   ObjectSetInteger(0, bg, OBJPROP_YSIZE,        boxH);
   ObjectSetInteger(0, bg, OBJPROP_BGCOLOR,      InpPanelBgColor);
   ObjectSetInteger(0, bg, OBJPROP_BORDER_TYPE,  BORDER_FLAT);
   ObjectSetInteger(0, bg, OBJPROP_COLOR,        InpPanelBorderColor);
   ObjectSetInteger(0, bg, OBJPROP_BACK,         false);
   ObjectSetInteger(0, bg, OBJPROP_SELECTABLE,   false);
   ObjectSetInteger(0, bg, OBJPROP_HIDDEN,       true);

   //--- lines. On a bottom corner the y axis runs upwards, so the order is
   //--- reversed to keep the text reading top to bottom either way.
   int textX = InpPanelX + padX;
   for(int i = 0; i < count; i++)
     {
      int y = PanelCornerIsLower()
              ? top + padY + (count - 1 - i) * lineH
              : top + padY + i * lineH;
      PanelLine(i, textX, y, lines[i]);
     }

   //--- drop any labels left over from a longer previous render
   long chart = ChartID();
   for(int i = ObjectsTotal(chart, -1, -1) - 1; i >= 0; i--)
     {
      string name = ObjectName(chart, i, -1, -1);
      if(StringFind(name, PANEL_PREFIX "L") != 0)
         continue;
      int idx = (int)StringToInteger(StringSubstr(name, StringLen(PANEL_PREFIX) + 1));
      if(idx >= count)
         ObjectDelete(chart, name);
     }

   ChartRedraw();
  }

void PanelHandleClick(const string clicked, const string block)
  {
   if(clicked != PANEL_TOGGLE)
      return;
   g_panelOpen = !g_panelOpen;
   ObjectSetInteger(0, PANEL_TOGGLE, OBJPROP_STATE, false);
   PanelRender(block);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  LIFECYCLE                                                       |
//|                                                                  |
//+------------------------------------------------------------------+
void ResolveBrokerClock()
  {
   if(InpBrokerOffsetMode == BOFF_MANUAL || IsTesting())
     {
      g_brokerWinterOffsetSec = InpBrokerWinterOffsetHours * 3600;
     }
   else
     {
      datetime utcNow = TimeGMT();
      int currentOffset = (int)MathRound((double)(TimeCurrent() - utcNow) / 3600.0) * 3600;
      if(DstActive(InpBrokerDSTRule, utcNow))
         currentOffset -= 3600;
      g_brokerWinterOffsetSec = currentOffset;
     }

   PrintFormat("[%s] Broker winter offset resolved to UTC%+.0f (DST rule: %s). "
               "Right now the server is UTC%+.1f.",
               InpTag, g_brokerWinterOffsetSec / 3600.0,
               (InpBrokerDSTRule == DST_US ? "US" : (InpBrokerDSTRule == DST_EU ? "EU" : "none")),
               BrokerOffsetAtUtc(BrokerToUtc(TimeCurrent())) / 3600.0);
  }

int OnInit()
  {
   IndicatorShortName(StringFormat("%s replay v2", InpTag));

   if(InpTPPctOfATR <= 0.0 || InpATRDays < 1 || InpDaysToShow < 1)
     {
      Print("Check InpTPPctOfATR, InpATRDays and InpDaysToShow - all must be positive.");
      return(INIT_PARAMETERS_INCORRECT);
     }
   if(InpPartialClosePct < 0.0 || InpPartialClosePct > 100.0)
     {
      Print("InpPartialClosePct must be between 0 and 100.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   g_pointsToPrice = Point;
   //--- a pip is ten points on a 3 or 5 digit feed, one point otherwise
   g_pipSize       = Point * ((Digits == 3 || Digits == 5) ? 10.0 : 1.0);
   g_lastBarCount  = 0;
   ResolveBrokerClock();

   //--- do NOT treat this first pass as the finished picture. MT4 has almost
   //--- certainly not loaded the other timeframes yet; OnCalculate rebuilds
   //--- as they arrive.
   Rebuild();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ClearObjects();
   PanelClear();
   CloseCSV();
   Comment("");
  }

//--- the toggle button
void OnChartEvent(const int id, const long &lparam, const double &dparam,
                  const string &sparam)
  {
   if(id == CHARTEVENT_OBJECT_CLICK)
      PanelHandleClick(sparam, g_panelBlock);
  }

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
   static datetime lastSignalBar = 0;

   //--- rebuild when a signal bar closes, and ALSO whenever more history has
   //--- arrived. The second condition is the one that matters on startup:
   //--- MT4 streams the other timeframes down over the first few seconds,
   //--- and without this the replay would keep whatever it managed to read
   //--- on the very first pass.
   int fingerprint = HistoryFingerprint();
   datetime currentBar = iTime(NULL, InpEntryTF, 0);

   if(currentBar != lastSignalBar || fingerprint != g_lastBarCount)
     {
      lastSignalBar  = currentBar;
      g_lastBarCount = fingerprint;
      Rebuild();
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
