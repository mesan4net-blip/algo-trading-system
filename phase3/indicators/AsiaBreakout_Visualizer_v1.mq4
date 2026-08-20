//+------------------------------------------------------------------+
//|                                  AsiaBreakout_Visualizer_v1.mq4  |
//|          History visualiser for AsiaBreakout_EA_v1 - shows every  |
//|          past setup, entry, stop and target the EA would have had |
//+------------------------------------------------------------------+
//
//  WHAT THIS IS
//    The EA's rules, replayed over history and drawn on the chart. For every
//    past trading day it rebuilds the Asia range and the trigger candle,
//    applies the same entry, stop and target rules, and draws the result:
//
//      shaded box      the Asia session range (and the trigger candle)
//      arrow           the entry, on the bar the trade would have opened
//      green line      the target, at the price it was set to
//      red line        the structural stop level
//      thick line      the trade itself, entry price to exit price,
//                      coloured by outcome
//      label           the R multiple and the exit reason
//
//    A panel totals it all up: trades, hit rate, average R, and how many
//    days were skipped and why.
//
//  IT MATCHES THE EA BECAUSE IT SHARES THE EA'S CODE
//    The whole TIME section below is a VERBATIM copy of the block in
//    AsiaBreakout_EA_v1.mq4. If you change a session rule in one, change it
//    in the other, or the picture stops describing the robot.
//
//  THE RULES BEING REPLAYED
//    Entry   a bar on the signal timeframe CLOSES beyond the level; the
//            trade opens at the OPEN of the following bar
//    Stop    a bar CLOSES back beyond the opposite level; exit at that close
//    Target  TOUCH - the bar's high (long) or low (short) reaching the target
//            is enough, no close required
//    Hard    everything is flat at the New York close
//
//    Within one bar the TARGET wins over the stop. That is not a tie-break,
//    it is the truth: the target is a resting order that would have filled
//    the moment price traded there, while the stop is not even evaluated
//    until the bar has closed.
//
//  WHAT IT CANNOT KNOW
//    Historical spread, slippage and swap. Entries are drawn at the raw bar
//    open and exits at the raw level, so the R multiples here are slightly
//    kinder than live trading. The EA's spread filter is therefore not
//    applied. Everything else is modelled exactly.
//
//  NOTHING REPAINTS
//    Only closed bars are read. A day that has been drawn will not change.
//
//+------------------------------------------------------------------+
#property copyright "algo-trading-system"
#property link      "https://github.com/mesan4net-blip/algo-trading-system"
#property version   "1.00"
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

#define DIR_NONE   0
#define DIR_LONG   1
#define DIR_SHORT -1

#define SLOT_ASIA    0
#define SLOT_TRIGGER 1
#define SLOT_COUNT   2

#define OBJ_PREFIX "ABVIZ_"

//--- exit reasons
#define EXIT_TARGET  0
#define EXIT_STOP    1
#define EXIT_NYCLOSE 2

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input string          _s01                       = "=== STRATEGY (match your EA) ==="; // .
input ENUM_STRAT_MODE InpMode                    = MODE_ASIA_RANGE;             // Which breakout to replay
input ENUM_TIMEFRAMES InpSignalTF                = PERIOD_H1;                   // Signal timeframe
input double          InpTPPctOfATR              = 80.0;                        // Target as % of 5-day ATR
input bool            InpTradeLongs              = true;                        // Replay long breakouts
input bool            InpTradeShorts             = true;                        // Replay short breakouts

input string          _s02                       = "=== ASIA SESSION ===";      // .
input ENUM_TZ         InpAsiaTZ                  = TZ_UTC;                      // Timezone the Asia hours are given in
input int             InpAsiaStartHour           = 22;                          // Asia start hour
input int             InpAsiaStartMin            = 0;                           // Asia start minute
input int             InpAsiaEndHour             = 9;                           // Asia end hour
input int             InpAsiaEndMin              = 0;                           // Asia end minute
input ENUM_TIMEFRAMES InpRangeTF                 = PERIOD_M15;                  // Timeframe used to measure the range

input string          _s03                       = "=== TRIGGER CANDLE ===";    // .
input ENUM_TZ         InpTriggerTZ               = TZ_LONDON;                   // Timezone the trigger hour is given in
input int             InpTriggerHour             = 8;                           // Trigger candle OPEN hour
input int             InpTriggerMin              = 0;                           // Trigger candle OPEN minute
input ENUM_TIMEFRAMES InpTriggerTF               = PERIOD_H1;                   // Trigger candle timeframe
input ENUM_CANDLE_SL_SRC InpCandleSLSource       = CSL_TRIGGER_CANDLE;          // Candle mode: stop/exit level source

input string          _s04                       = "=== 5-DAY ATR ===";         // .
input int             InpATRDays                 = 5;                           // ATR lookback in daily bars
input bool            InpATRSkipSunday           = true;                        // Skip the broker's stunted Sunday bar

input string          _s05                       = "=== FILTERS ===";           // .
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

input string          _s06                       = "=== TRADE CONTROL ===";     // .
input int             InpMaxTradesPerDay         = 1;                           // Max entries per flavor per day
input bool            InpAllowReEntryAfterStop   = false;                       // Re-enter same direction after a stop-out
input bool            InpAllowOppositeSameDay    = false;                       // Take the opposite side after a stop-out

input string          _s07                       = "=== HARD EXIT (NY CLOSE) ==="; // .
input ENUM_TZ         InpNYCloseTZ               = TZ_NEWYORK;                  // Timezone the NY close is given in
input int             InpNYCloseHour             = 17;                          // NY close hour
input int             InpNYCloseMin              = 0;                           // NY close minute
input bool            InpFridayEarlyClose        = false;                       // Use a different close time on Friday
input int             InpFridayCloseHour         = 16;                          // Friday close hour
input int             InpFridayCloseMin          = 0;                           // Friday close minute

input string          _s08                       = "=== BROKER CLOCK ===";      // .
input ENUM_OFFSET_MODE InpBrokerOffsetMode       = BOFF_AUTO;                   // How to learn the server GMT offset
input int             InpBrokerWinterOffsetHours = 2;                           // Server offset from UTC in WINTER
input ENUM_DST_RULE   InpBrokerDSTRule           = DST_US;                      // Does the server clock shift, and how

input string          _s09                       = "=== DISPLAY ===";           // .
input int             InpDaysToShow              = 60;                          // Trading days to replay
input bool            InpShowAsiaBox             = true;                        // Draw the Asia range box
input bool            InpShowTriggerBox          = true;                        // Draw the trigger candle box
input bool            InpShowLevels              = true;                        // Draw the stop and target lines
input bool            InpShowLabels              = true;                        // Label each trade with its R multiple
input bool            InpShowSkips               = true;                        // Mark days that were skipped, and why
input bool            InpShowPanel               = true;                        // Show the summary panel
input color           InpColorAsia               = C'40,60,90';                 // Asia box
input color           InpColorTrigger            = C'90,60,20';                 // Trigger candle box
input color           InpColorWin                = clrMediumSeaGreen;           // Winning trade
input color           InpColorLoss               = clrIndianRed;                // Losing trade
input color           InpColorFlat               = clrGoldenrod;                // Exited at the NY close
input color           InpColorSkip               = clrDimGray;                  // Skipped day

input string          _s10                       = "=== EXPORT ===";            // .
input bool            InpExportCSV               = false;                       // Write the replayed trades to a CSV
input string          InpTag                     = "AsiaBO";                    // Name used in logs and the CSV

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
int    g_brokerWinterOffsetSec = 0;
double g_pointsToPrice         = 0.0;
int    g_objCount              = 0;
int    g_csvHandle             = INVALID_HANDLE;

//--- per-slot tallies
int    g_nTrades[SLOT_COUNT];
int    g_nWins[SLOT_COUNT];
int    g_nLosses[SLOT_COUNT];
int    g_nFlat[SLOT_COUNT];
double g_sumR[SLOT_COUNT];
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
             "exit_time", "exit", "reason", "r_multiple");
   PrintFormat("[%s] writing replay to MQL4/Files/%s", InpTag, file);
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
//|  THE REPLAY                                                      |
//|                                                                  |
//|  One trading day, one flavor. Returns the number of trades drawn. |
//+------------------------------------------------------------------+
int ReplayDay(const datetime nyClose, const int slot)
  {
   int period = PeriodSeconds(InpSignalTF);
   if(period <= 0)
      return(0);

   //--- 1. the levels this day would have traded -------------------------
   double levelHigh = 0, levelLow = 0, stopHigh = 0, stopLow = 0;
   datetime levelReadyAt = 0;
   datetime boxFrom = 0, boxTo = 0;

   datetime asiaStart = 0, asiaEnd = 0;
   double   asiaHigh = 0, asiaLow = 0;
   bool     asiaOk = false;

   ResolveCompletedSession(nyClose, InpAsiaTZ,
                           InpAsiaStartHour, InpAsiaStartMin,
                           InpAsiaEndHour,   InpAsiaEndMin,
                           asiaStart, asiaEnd);
   asiaOk = RangeInWindow(InpRangeTF, asiaStart, asiaEnd, asiaHigh, asiaLow);

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

   //--- the level must belong to THIS trading day, exactly as the EA insists
   if(levelReadyAt <= PrevHardExit(nyClose - 60) || levelReadyAt >= nyClose)
     { g_nSkipNoData[slot]++; return(0); }

   if(!WeekdayAllowedAt(levelReadyAt))
     { g_nSkipFilter[slot]++; return(0); }

   g_nDays[slot]++;

   //--- 2. draw the range box --------------------------------------------
   bool wantBox = (slot == SLOT_ASIA) ? InpShowAsiaBox : InpShowTriggerBox;
   if(wantBox)
      PaintBox(boxFrom, levelHigh, boxTo, levelLow,
               (slot == SLOT_ASIA) ? InpColorAsia : InpColorTrigger);

   //--- 3. the filters that kill a whole day ------------------------------
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

   double target = InpTPPctOfATR / 100.0 * atr5;
   double buffer = InpBreakoutBufferPoints * g_pointsToPrice;

   //--- 4. walk the bars ---------------------------------------------------
   int startShift = iBarShift(NULL, InpSignalTF, levelReadyAt, false);
   int endShift   = iBarShift(NULL, InpSignalTF, nyClose - 1, false);
   if(startShift < 0 || endShift < 0 || startShift < endShift)
     { g_nSkipNoData[slot]++; return(0); }

   int    taken       = 0;
   int    lastStopDir = DIR_NONE;
   bool   sawBar      = false;
   string skipNote    = "";

   int k = startShift;
   while(k >= endShift && taken < InpMaxTradesPerDay)
     {
      datetime barOpen  = iTime(NULL, InpSignalTF, k);
      datetime barClose = barOpen + period;

      if(barClose <= levelReadyAt) { k--; continue; }   // bar predates the level
      if(barOpen  >= nyClose)      break;
      if(barClose + InpNoNewTradesBeforeCloseM*60 >= nyClose) break;
      sawBar = true;

      //--- entry is CLOSE-based
      double c = iClose(NULL, InpSignalTF, k);
      int dir = DIR_NONE;
      if(c > levelHigh + buffer)      dir = DIR_LONG;
      else if(c < levelLow - buffer)  dir = DIR_SHORT;
      if(dir == DIR_NONE) { k--; continue; }

      if((dir == DIR_LONG && !InpTradeLongs) || (dir == DIR_SHORT && !InpTradeShorts))
        { k--; continue; }

      if(lastStopDir != DIR_NONE)
        {
         if(dir == lastStopDir && !InpAllowReEntryAfterStop) break;
         if(dir != lastStopDir && !InpAllowOppositeSameDay)  break;
        }

      //--- the trade opens at the OPEN of the following bar
      int entryShift = k - 1;
      if(entryShift < 0) break;
      //--- the entry bar must still be inside the day, or there is nothing to
      //--- scan for an exit and k would stop decreasing
      if(entryShift < endShift) break;
      datetime entryTime  = iTime(NULL, InpSignalTF, entryShift);
      if(entryTime >= nyClose) break;
      double   entryPrice = iOpen(NULL, InpSignalTF, entryShift);

      double structural = (dir == DIR_LONG) ? stopLow : stopHigh;
      double tp         = (dir == DIR_LONG) ? stopLow + target : stopHigh - target;

      if(InpMaxSLPoints > 0 &&
         MathAbs(entryPrice - structural) / g_pointsToPrice > InpMaxSLPoints)
        {
         g_nSkipFilter[slot]++;
         skipNote = "stop too far";
         k--; continue;
        }

      //--- the edge case: range wider than the ATR-derived target
      bool targetBehind = (dir == DIR_LONG) ? (tp <= entryPrice) : (tp >= entryPrice);
      if(targetBehind)
        {
         g_nSkipTarget[slot]++;
         skipNote = "target behind entry";
         if(InpShowSkips)
            PaintText(entryTime, (dir == DIR_LONG) ? levelHigh : levelLow,
                      " target behind entry", InpColorSkip);
         k--; continue;
        }

      //--- 5. how the trade ends -------------------------------------------
      int      reason    = EXIT_NYCLOSE;
      double   exitPrice = 0.0;
      datetime exitTime  = 0;
      int      exitShift = endShift;

      for(int j = entryShift; j >= endShift; j--)
        {
         double hi = iHigh(NULL, InpSignalTF, j);
         double lo = iLow(NULL, InpSignalTF, j);
         double cl = iClose(NULL, InpSignalTF, j);

         //--- TARGET FIRST, and not as a tie-break: the target is a resting
         //--- order that fills the moment price trades there, while the stop
         //--- is not even looked at until the bar has closed.
         bool hitTarget = (dir == DIR_LONG) ? (hi >= tp) : (lo <= tp);
         if(hitTarget)
           {
            reason = EXIT_TARGET;  exitPrice = tp;
            exitTime = iTime(NULL, InpSignalTF, j) + period;
            exitShift = j;
            break;
           }

         bool hitStop = (dir == DIR_LONG) ? (cl < structural) : (cl > structural);
         if(hitStop)
           {
            reason = EXIT_STOP;  exitPrice = cl;
            exitTime = iTime(NULL, InpSignalTF, j) + period;
            exitShift = j;
            break;
           }

         if(j == endShift)
           {
            reason = EXIT_NYCLOSE;  exitPrice = cl;
            exitTime = iTime(NULL, InpSignalTF, j) + period;
            exitShift = j;
           }
        }

      //--- 6. score it -------------------------------------------------------
      double risk = MathAbs(entryPrice - structural);
      double r    = (risk > 0.0)
                    ? ((dir == DIR_LONG) ? (exitPrice - entryPrice) : (entryPrice - exitPrice)) / risk
                    : 0.0;

      g_nTrades[slot]++;
      g_sumR[slot] += r;
      if(g_nTrades[slot] == 1) { g_bestR[slot] = r; g_worstR[slot] = r; }
      g_bestR[slot]  = MathMax(g_bestR[slot], r);
      g_worstR[slot] = MathMin(g_worstR[slot], r);
      if(reason == EXIT_TARGET)       g_nWins[slot]++;
      else if(reason == EXIT_STOP)    g_nLosses[slot]++;
      else                            g_nFlat[slot]++;

      //--- 7. draw it --------------------------------------------------------
      color clr = (reason == EXIT_TARGET) ? InpColorWin
                : (reason == EXIT_STOP)   ? InpColorLoss
                                          : InpColorFlat;
      string reasonText = (reason == EXIT_TARGET) ? "TP"
                        : (reason == EXIT_STOP)   ? "SL"
                                                  : "NY";

      PaintArrow(entryTime, entryPrice, (dir == DIR_LONG) ? 233 : 234, clr,
                 StringFormat("%s %s entry %s", SlotName(slot),
                              (dir == DIR_LONG) ? "long" : "short",
                              DoubleToString(entryPrice, Digits)));
      PaintSegment(entryTime, entryPrice, exitTime, exitPrice, clr, STYLE_SOLID, 2);

      if(InpShowLevels)
        {
         PaintSegment(entryTime, tp, exitTime, tp, InpColorWin, STYLE_DOT, 1);
         PaintSegment(entryTime, structural, exitTime, structural, InpColorLoss, STYLE_DOT, 1);
        }

      if(InpShowLabels)
         PaintText(exitTime, exitPrice,
                   StringFormat(" %s %+.2fR", reasonText, r), clr);

      if(g_csvHandle != INVALID_HANDLE)
         FileWrite(g_csvHandle,
                   TimeToString(levelReadyAt, TIME_DATE),
                   SlotName(slot),
                   (dir == DIR_LONG) ? "LONG" : "SHORT",
                   DoubleToString(levelHigh, Digits),
                   DoubleToString(levelLow, Digits),
                   DoubleToString(atr5, Digits),
                   TimeToString(entryTime, TIME_DATE|TIME_MINUTES),
                   DoubleToString(entryPrice, Digits),
                   DoubleToString(structural, Digits),
                   DoubleToString(tp, Digits),
                   TimeToString(exitTime, TIME_DATE|TIME_MINUTES),
                   DoubleToString(exitPrice, Digits),
                   reasonText,
                   DoubleToString(r, 3));

      taken++;
      if(reason == EXIT_STOP)
         lastStopDir = dir;

      //--- the exit bar's own close can be the next entry signal
      k = exitShift;
     }

   if(taken == 0 && sawBar && StringLen(skipNote) == 0)
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
      Comment("");
      return;
     }

   string text = StringFormat("%s replay  %s  %s   %d trading days\n",
                              InpTag, Symbol(),
                              StringSubstr(EnumToString(InpSignalTF), 7),
                              daysWalked);
   text += StringFormat("Target %.0f%% of ATR%d from the level | entry & stop on CLOSE | target on TOUCH\n\n",
                        InpTPPctOfATR, InpATRDays);

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      if(!SlotEnabled(slot))
         continue;

      int n = g_nTrades[slot];
      text += StringFormat("%-7s %d setups traded of %d days\n",
                           SlotName(slot), n, g_nDays[slot]);

      if(n > 0)
        {
         double hitRate = 100.0 * g_nWins[slot] / n;
         double avgR    = g_sumR[slot] / n;
         text += StringFormat("        target %d (%.0f%%)  stop %d  NY close %d\n",
                              g_nWins[slot], hitRate, g_nLosses[slot], g_nFlat[slot]);
         text += StringFormat("        total %+.2fR   avg %+.2fR   best %+.2fR   worst %+.2fR\n",
                              g_sumR[slot], avgR, g_bestR[slot], g_worstR[slot]);
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

   text += "R is measured against the STRUCTURAL stop. Spread, slippage and\n";
   text += "swap are not modelled, so live results will be slightly worse.\n";

   Comment(text);
  }

//+------------------------------------------------------------------+
//| Run the whole replay                                             |
//+------------------------------------------------------------------+
void Rebuild()
  {
   ClearObjects();
   CloseCSV();
   OpenCSV();

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      g_nTrades[slot] = 0;  g_nWins[slot] = 0;  g_nLosses[slot] = 0;
      g_nFlat[slot]   = 0;  g_sumR[slot]  = 0;  g_bestR[slot]   = 0;
      g_worstR[slot]  = 0;  g_nDays[slot] = 0;
      g_nSkipNoBreak[slot] = 0;  g_nSkipTarget[slot] = 0;
      g_nSkipFilter[slot]  = 0;  g_nSkipNoData[slot] = 0;
     }

   datetime nyClose = PrevHardExit(TimeCurrent());
   int daysWalked = 0;

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

   PrintFormat("[%s] replayed %d trading days, drew %d objects.",
               InpTag, daysWalked, g_objCount);
   if(g_objCount >= MAX_OBJECTS)
      PrintFormat("[%s] hit the %d object cap - the oldest days are not drawn. "
                  "Lower InpDaysToShow or turn off some of the display options. "
                  "The panel totals still cover every day replayed.",
                  InpTag, MAX_OBJECTS);
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
   IndicatorShortName(StringFormat("%s replay", InpTag));

   if(InpTPPctOfATR <= 0.0 || InpATRDays < 1 || InpDaysToShow < 1)
     {
      Print("Check InpTPPctOfATR, InpATRDays and InpDaysToShow - all must be positive.");
      return(INIT_PARAMETERS_INCORRECT);
     }

   g_pointsToPrice = Point;
   ResolveBrokerClock();
   Rebuild();
   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ClearObjects();
   CloseCSV();
   Comment("");
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
   //--- the replay only changes when a signal bar closes, so rebuild then and
   //--- not on every tick
   static datetime lastSignalBar = 0;
   datetime currentBar = iTime(NULL, InpSignalTF, 0);

   if(currentBar != lastSignalBar)
     {
      lastSignalBar = currentBar;
      Rebuild();
     }

   return(rates_total);
  }
//+------------------------------------------------------------------+
