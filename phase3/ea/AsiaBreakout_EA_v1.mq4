//+------------------------------------------------------------------+
//|                                        AsiaBreakout_EA_v1.mq4    |
//|            Asia Session / Trigger Candle breakout Expert Advisor |
//+------------------------------------------------------------------+
//
//  WHAT THIS IS
//    One EA that trades two related breakout patterns on a single pair.
//
//      MODE_ASIA_RANGE     Levels are the high/low of the Asia session.
//      MODE_TRIGGER_CANDLE Levels are the high/low of ONE nominated candle
//                          (default: the first hour of London).
//      MODE_BOTH           Both, on separate magic numbers.
//
//  THE THREE SIGNAL RULES - these are deliberately NOT symmetrical
//
//    ENTRY  = CLOSE.  A bar on the signal timeframe must CLOSE beyond the
//                     level. A wick through it is not a breakout.
//    STOP   = CLOSE.  A bar must CLOSE back beyond the opposite level to
//                     stop the trade out. Price may trade well past the
//                     level intrabar and the trade survives, provided the
//                     bar closes back on the right side.
//    TARGET = TOUCH.  The take profit is a real broker TP order. Price only
//                     has to trade there. No close required.
//
//  WHY THERE IS STILL A BROKER STOP ON THE ORDER
//    A close-based stop means the EA, not the broker, decides when to exit.
//    If the terminal or the VPS drops, nothing protects the position. So a
//    DISASTER STOP is placed with the order, parked well beyond the
//    structural level (default 25% of the 5-day ATR past it) so it cannot
//    pre-empt the close-based rule in normal conditions but will catch a
//    gap, a flash move, or a dead VPS. Set InpProtectiveSLMode = PSL_NONE
//    to trade naked, at your own risk.
//
//  TARGETS
//    TP is a percentage (default 80%) of the 5-day ATR, measured FROM THE
//    STRUCTURAL LEVEL, not from the entry price:
//
//      Asia long    TP = AsiaLow      + 0.80 * ATR5
//      Asia short   TP = AsiaHigh     - 0.80 * ATR5
//      Candle long  TP = TriggerLow   + 0.80 * ATR5
//      Candle short TP = TriggerHigh  - 0.80 * ATR5
//
//    So the span from the structural stop to the target is 80% of ATR5.
//    When the range is WIDER than 80% of ATR5 the target lands at or below
//    the entry - an unwinnable trade. Those days are SKIPPED and logged.
//
//  DAYLIGHT SAVING
//    Every session is defined in its own real timezone and converted with
//    real DST rules (EU rules for London, US rules for New York, none for
//    Tokyo). See the TIME section below. The broker's own clock is handled
//    separately - most brokers, including FOREX.com, run a New-York-DST
//    clock at UTC+2 winter / UTC+3 summer.
//
//  HARD STOP
//    Every position is closed at the New York session close, regardless of
//    P/L and regardless of how near the target is.
//
//  ONE TRADE AT A TIME
//    Enforced per symbol. In MODE_BOTH the two flavors have their own magic
//    numbers, and InpOneTradeAcrossModes (default true) additionally stops
//    them from being in the market at the same time.
//
//  SIGNAL TIMING
//    Everything reads CLOSED bars only (shift >= 1). The developing bar is
//    used for drawing and for the hard-exit clock, never for a signal. A
//    signal that appears cannot later vanish.
//
//+------------------------------------------------------------------+
#property copyright "algo-trading-system"
#property link      "https://github.com/mesan4net-blip/algo-trading-system"
#property version   "1.00"
#property strict

//+------------------------------------------------------------------+
//| Enumerations                                                     |
//+------------------------------------------------------------------+
enum ENUM_STRAT_MODE
  {
   MODE_ASIA_RANGE      = 0,  // Asia session range breakout
   MODE_TRIGGER_CANDLE  = 1,  // Trigger candle breakout
   MODE_BOTH            = 2   // Both (separate magic numbers)
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
   DST_US   = 1,  // Broker follows US/New York DST (FOREX.com, most MT4)
   DST_EU   = 2   // Broker follows EU/London DST
  };

enum ENUM_OFFSET_MODE
  {
   BOFF_AUTO   = 0,  // Auto-detect from terminal (live only)
   BOFF_MANUAL = 1   // Use InpBrokerWinterOffsetHours
  };

enum ENUM_LOT_MODE
  {
   LOT_FIXED        = 0,  // Fixed lot size
   LOT_RISK_PERCENT = 1   // Percent of equity risked to the structural stop
  };

enum ENUM_CANDLE_SL_SRC
  {
   CSL_TRIGGER_CANDLE = 0,  // Trigger candle low/high
   CSL_ASIA_SESSION   = 1   // Asia session low/high
  };

enum ENUM_PSL_MODE
  {
   PSL_NONE    = 0,  // No broker stop at all (VPS failure = unlimited risk)
   PSL_ATR_PCT = 1,  // Percent of ATR5 beyond the structural level
   PSL_POINTS  = 2   // Fixed points beyond the structural level
  };

//--- internal direction codes
#define DIR_NONE   0
#define DIR_LONG   1
#define DIR_SHORT -1

//--- internal slot indexes (one per flavor)
#define SLOT_ASIA    0
#define SLOT_TRIGGER 1
#define SLOT_COUNT   2

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input string          _s01                       = "=== STRATEGY ===";          // .
input ENUM_STRAT_MODE InpMode                    = MODE_ASIA_RANGE;             // Which breakout to trade
input ENUM_TIMEFRAMES InpSignalTF                = PERIOD_H1;                   // Signal timeframe (entry + stop closes)
input double          InpTPPctOfATR              = 80.0;                        // Target as % of 5-day ATR
input bool            InpTradeLongs              = true;                        // Allow long breakouts
input bool            InpTradeShorts             = true;                        // Allow short breakouts

input string          _s02                       = "=== ASIA SESSION ===";      // .
input ENUM_TZ         InpAsiaTZ                  = TZ_UTC;                      // Timezone the Asia hours are given in
input int             InpAsiaStartHour           = 0;                           // Asia start hour
input int             InpAsiaStartMin            = 0;                           // Asia start minute
input int             InpAsiaEndHour             = 8;                           // Asia end hour
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

input string          _s05                       = "=== ENTRY FILTERS ===";     // .
input int             InpBreakoutBufferPoints    = 0;                           // Extra points beyond level to confirm
input int             InpMaxSpreadPoints         = 30;                          // Max spread to accept an entry (points)
input int             InpMinRangePoints          = 0;                           // Skip if range narrower than this (0=off)
input int             InpMaxRangePoints          = 0;                           // Skip if range wider than this (0=off)
input int             InpMaxSLPoints             = 0;                           // Skip if structural stop farther than this (0=off)
input int             InpNoNewTradesBeforeCloseM = 30;                          // No new entries within N min of NY close
input bool            InpTradeMon                = true;                        // Trade Monday
input bool            InpTradeTue                = true;                        // Trade Tuesday
input bool            InpTradeWed                = true;                        // Trade Wednesday
input bool            InpTradeThu                = true;                        // Trade Thursday
input bool            InpTradeFri                = true;                        // Trade Friday

input string          _s06                       = "=== TRADE CONTROL ===";     // .
input int             InpMaxTradesPerDay         = 1;                           // Max entries per flavor per day
input bool            InpAllowReEntryAfterStop   = false;                       // Re-enter same direction after a stop-out
input bool            InpAllowOppositeSameDay    = false;                       // Take the opposite side after a stop-out
input bool            InpOneTradeAcrossModes     = true;                        // In MODE_BOTH, only one open trade total

input string          _s07                       = "=== RISK ===";              // .
input ENUM_LOT_MODE   InpLotMode                 = LOT_FIXED;                   // Position sizing method
input double          InpFixedLots               = 0.10;                        // Fixed lot size
input double          InpRiskPercent             = 1.0;                         // Risk % of equity (structural stop distance)
input ENUM_PSL_MODE   InpProtectiveSLMode        = PSL_ATR_PCT;                 // Disaster stop placed with the order
input double          InpProtectiveSLATRPct      = 25.0;                        // Disaster stop: % of ATR5 beyond level
input int             InpProtectiveSLPoints      = 300;                         // Disaster stop: points beyond level

input string          _s08                       = "=== HARD EXIT (NY CLOSE) ==="; // .
input ENUM_TZ         InpNYCloseTZ               = TZ_NEWYORK;                  // Timezone the NY close is given in
input int             InpNYCloseHour             = 17;                          // NY close hour
input int             InpNYCloseMin              = 0;                           // NY close minute
input bool            InpFridayEarlyClose        = false;                       // Use a different close time on Friday
input int             InpFridayCloseHour         = 16;                          // Friday close hour
input int             InpFridayCloseMin          = 0;                           // Friday close minute

input string          _s09                       = "=== BROKER CLOCK ===";      // .
input ENUM_OFFSET_MODE InpBrokerOffsetMode       = BOFF_AUTO;                   // How to learn the server GMT offset
input int             InpBrokerWinterOffsetHours = 2;                           // Server offset from UTC in WINTER
input ENUM_DST_RULE   InpBrokerDSTRule           = DST_US;                      // Does the server clock shift, and by which rules

input string          _s10                       = "=== EXECUTION ===";         // .
input int             InpSlippagePoints          = 5;                           // Max slippage (points)
input int             InpOrderRetries            = 3;                           // Retries on a failed order
input int             InpMagicAsia               = 8801;                        // Magic number, Asia range flavor
input int             InpMagicTrigger            = 8802;                        // Magic number, trigger candle flavor
input string          InpTradeComment            = "AsiaBO";                    // Order comment prefix

input string          _s11                       = "=== DISPLAY / LOG ===";     // .
input bool            InpDrawObjects             = true;                        // Draw levels and boxes on the chart
input bool            InpShowPanel               = true;                        // Show the status panel
input bool            InpWriteCSVLog             = true;                        // Write a CSV trade log
input color           InpColorRange              = clrSteelBlue;                // Range box colour
input color           InpColorTP                 = clrSeaGreen;                 // Target line colour
input color           InpColorSL                 = clrFireBrick;                // Stop line colour

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
int      g_brokerWinterOffsetSec = 0;      // resolved on init
double   g_pointsToPrice         = 0.0;    // Point, cached
int      g_stopLevelPoints       = 0;      // broker minimum stop distance

//--- per-day state
datetime g_dayKey                = 0;      // broker date of the current trading day
double   g_atr5                  = 0.0;    // cached 5-day ATR (price units)
datetime g_atrDay                = 0;      // day the ATR was computed for

//--- Asia range, resolved once its window has ended
bool     g_asiaReady   = false;
double   g_asiaHigh    = 0.0;
double   g_asiaLow     = 0.0;
datetime g_asiaStartB  = 0;
datetime g_asiaEndB    = 0;

//--- trigger candle, resolved once the candle has closed
bool     g_trigReady   = false;
double   g_trigHigh    = 0.0;
double   g_trigLow     = 0.0;
datetime g_trigOpenB   = 0;

//--- per-slot bookkeeping
int      g_tradesToday[SLOT_COUNT];        // entries taken today
int      g_lastStopDir[SLOT_COUNT];        // direction of the last stop-out today
datetime g_lastSignalBar[SLOT_COUNT];      // last signal bar processed
double   g_exitLevel[SLOT_COUNT];          // close-based stop level of the open trade
int      g_openDir[SLOT_COUNT];            // direction of the open trade
int      g_openTicket[SLOT_COUNT];         // ticket of the open trade, for reconciliation

string   g_skipReason[SLOT_COUNT];         // why today was skipped, for the panel

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
//|  5-DAY ATR                                                       |
//|                                                                  |
//|  Computed by hand rather than with iATR() for one reason: many    |
//|  brokers, FOREX.com included, print a stunted Sunday daily bar    |
//|  covering only the two or three hours between the week's open and |
//|  midnight server time. Feeding that into a 5-day average drags it |
//|  down materially and shrinks every target the EA sets. Sunday     |
//|  bars are skipped and the window reaches further back to keep the |
//|  requested number of real trading days.                           |
//+------------------------------------------------------------------+
double ComputeATR()
  {
   int wanted = MathMax(1, InpATRDays);
   int collected = 0;
   double sum = 0.0;

   //--- shift 1 onwards: completed daily bars only
   for(int shift = 1; shift <= wanted*4 + 10 && collected < wanted; shift++)
     {
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

//+------------------------------------------------------------------+
//|                                                                  |
//|  LEVEL BUILDERS                                                  |
//|                                                                  |
//+------------------------------------------------------------------+

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

   //--- walk backwards from the last bar of the window to the first
   int maxBars = (int)((endBroker - startBroker) / barSeconds) + 4;
   for(int i = 0; i < maxBars; i++)
     {
      int s = shift + i;
      datetime barOpen = iTime(NULL, tf, s);
      if(barOpen == 0)
         break;
      if(barOpen < startBroker)
         break;

      //--- only bars that both open AND close inside the window count, so a
      //--- bar straddling the boundary can never leak outside prices in
      if(barOpen + barSeconds <= endBroker)
        {
         high = MathMax(high, iHigh(NULL, tf, s));
         low  = MathMin(low,  iLow(NULL, tf, s));
         found = true;
        }
     }

   return(found && high > low);
  }

//--- resolve the most recently completed Asia session
void UpdateAsiaRange(const datetime nowBroker)
  {
   datetime startB, endB;
   ResolveCompletedSession(nowBroker, InpAsiaTZ,
                           InpAsiaStartHour, InpAsiaStartMin,
                           InpAsiaEndHour,   InpAsiaEndMin,
                           startB, endB);

   if(g_asiaReady && startB == g_asiaStartB && endB == g_asiaEndB)
      return;                                   // already have this instance

   double high, low;
   if(!RangeInWindow(InpRangeTF, startB, endB, high, low))
     {
      g_asiaReady = false;
      return;
     }

   g_asiaStartB = startB;
   g_asiaEndB   = endB;
   g_asiaHigh   = high;
   g_asiaLow    = low;
   g_asiaReady  = true;

   PrintFormat("[%s] Asia range %s .. %s  H=%s L=%s  (%.0f pts)",
               InpTradeComment,
               TimeToString(startB, TIME_DATE|TIME_MINUTES),
               TimeToString(endB,   TIME_DATE|TIME_MINUTES),
               DoubleToString(high, Digits), DoubleToString(low, Digits),
               (high - low) / g_pointsToPrice);
  }

//--- resolve the most recently closed trigger candle
void UpdateTriggerCandle(const datetime nowBroker)
  {
   int barSeconds = PeriodSeconds(InpTriggerTF);
   if(barSeconds <= 0)
      return;

   //--- the candle must be fully closed, hence minSecondsInPast = one bar
   datetime openB = ResolvePastLocalTime(nowBroker, InpTriggerTZ,
                                         InpTriggerHour, InpTriggerMin,
                                         barSeconds);

   if(g_trigReady && openB == g_trigOpenB)
      return;

   int shift = iBarShift(NULL, InpTriggerTF, openB, true);
   if(shift < 0)
     {
      //--- no bar starts exactly there. Usually means the trigger minute does
      //--- not line up with the timeframe's bar grid, or the bar is missing
      //--- from history.
      g_trigReady = false;
      return;
     }

   g_trigOpenB = openB;
   g_trigHigh  = iHigh(NULL, InpTriggerTF, shift);
   g_trigLow   = iLow(NULL, InpTriggerTF, shift);
   g_trigReady = (g_trigHigh > g_trigLow);

   if(g_trigReady)
      PrintFormat("[%s] Trigger candle %s  H=%s L=%s  (%.0f pts)",
                  InpTradeComment,
                  TimeToString(openB, TIME_DATE|TIME_MINUTES),
                  DoubleToString(g_trigHigh, Digits),
                  DoubleToString(g_trigLow, Digits),
                  (g_trigHigh - g_trigLow) / g_pointsToPrice);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  SLOT HELPERS                                                    |
//|                                                                  |
//+------------------------------------------------------------------+
int SlotMagic(const int slot)
  {
   return(slot == SLOT_ASIA ? InpMagicAsia : InpMagicTrigger);
  }

string SlotName(const int slot)
  {
   return(slot == SLOT_ASIA ? "ASIA" : "CANDLE");
  }

bool SlotEnabled(const int slot)
  {
   if(InpMode == MODE_BOTH)
      return(true);
   if(slot == SLOT_ASIA)
      return(InpMode == MODE_ASIA_RANGE);
   return(InpMode == MODE_TRIGGER_CANDLE);
  }

//--- the breakout levels a slot trades: 'high'/'low' are the entry levels,
//--- 'stopHigh'/'stopLow' are the structural stop and target anchors.
bool SlotLevels(const int slot, double &high, double &low,
                double &stopHigh, double &stopLow)
  {
   if(slot == SLOT_ASIA)
     {
      if(!g_asiaReady)
         return(false);
      high = g_asiaHigh;  low = g_asiaLow;
      stopHigh = g_asiaHigh;  stopLow = g_asiaLow;
      return(true);
     }

   if(!g_trigReady)
      return(false);
   high = g_trigHigh;  low = g_trigLow;

   //--- the stop/exit level can optionally be taken from the Asia session
   //--- instead of the trigger candle itself
   if(InpCandleSLSource == CSL_ASIA_SESSION)
     {
      if(!g_asiaReady)
         return(false);
      stopHigh = g_asiaHigh;  stopLow = g_asiaLow;
     }
   else
     {
      stopHigh = g_trigHigh;  stopLow = g_trigLow;
     }
   return(true);
  }

//--- the close-based stop level of an open trade is remembered across
//--- restarts, because it belongs to the session the trade was opened in and
//--- that session's levels may already have rolled over.
string ExitLevelVarName(const int slot)
  {
   return(StringFormat("ABEA_%s_%d_EXIT", Symbol(), SlotMagic(slot)));
  }

string ExitDirVarName(const int slot)
  {
   return(StringFormat("ABEA_%s_%d_DIR", Symbol(), SlotMagic(slot)));
  }

string ExitTicketVarName(const int slot)
  {
   return(StringFormat("ABEA_%s_%d_TICKET", Symbol(), SlotMagic(slot)));
  }

void RememberExitLevel(const int slot, const int dir, const double level, const int ticket)
  {
   g_openDir[slot]    = dir;
   g_exitLevel[slot]  = level;
   g_openTicket[slot] = ticket;
   GlobalVariableSet(ExitLevelVarName(slot),  level);
   GlobalVariableSet(ExitDirVarName(slot),    (double)dir);
   GlobalVariableSet(ExitTicketVarName(slot), (double)ticket);
  }

void ForgetExitLevel(const int slot)
  {
   g_openDir[slot]    = DIR_NONE;
   g_exitLevel[slot]  = 0.0;
   g_openTicket[slot] = 0;
   GlobalVariableDel(ExitLevelVarName(slot));
   GlobalVariableDel(ExitDirVarName(slot));
   GlobalVariableDel(ExitTicketVarName(slot));
  }

void RecallExitLevel(const int slot)
  {
   if(g_exitLevel[slot] > 0.0)
      return;
   if(GlobalVariableCheck(ExitLevelVarName(slot)))
     {
      g_exitLevel[slot] = GlobalVariableGet(ExitLevelVarName(slot));
      g_openDir[slot]   = (int)GlobalVariableGet(ExitDirVarName(slot));
      if(GlobalVariableCheck(ExitTicketVarName(slot)))
         g_openTicket[slot] = (int)GlobalVariableGet(ExitTicketVarName(slot));
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  ORDER PLUMBING                                                  |
//|                                                                  |
//+------------------------------------------------------------------+
int CountOpen(const int magic)
  {
   int count = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() != Symbol())
         continue;
      if(magic != 0 && OrderMagicNumber() != magic)
         continue;
      if(OrderType() != OP_BUY && OrderType() != OP_SELL)
         continue;
      count++;
     }
   return(count);
  }

int CountOpenAnySlot()
  {
   return(CountOpen(InpMagicAsia) + CountOpen(InpMagicTrigger));
  }

//--- select the open position of a slot, if there is one
bool SelectSlotOrder(const int slot)
  {
   int magic = SlotMagic(slot);
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != magic)
         continue;
      if(OrderType() == OP_BUY || OrderType() == OP_SELL)
         return(true);
     }
   return(false);
  }

double NormalizePrice(const double price)
  {
   return(NormalizeDouble(price, Digits));
  }

double NormalizeLots(double lots)
  {
   double minLot  = MarketInfo(Symbol(), MODE_MINLOT);
   double maxLot  = MarketInfo(Symbol(), MODE_MAXLOT);
   double lotStep = MarketInfo(Symbol(), MODE_LOTSTEP);
   if(lotStep <= 0.0)
      lotStep = 0.01;

   lots = MathFloor(lots / lotStep + 0.0000001) * lotStep;
   lots = MathMax(lots, minLot);
   lots = MathMin(lots, maxLot);

   //--- lot step can be 0.01 or 0.1; two decimals covers both
   return(NormalizeDouble(lots, 2));
  }

//--- size from the STRUCTURAL stop distance. Note that because the real stop
//--- is close-based, the realised loss can exceed this - the structural
//--- distance is the planned risk, not a guaranteed one.
double ComputeLots(const double entry, const double structuralStop)
  {
   if(InpLotMode == LOT_FIXED)
      return(NormalizeLots(InpFixedLots));

   double distance = MathAbs(entry - structuralStop);
   if(distance <= 0.0)
      return(NormalizeLots(InpFixedLots));

   double tickValue = MarketInfo(Symbol(), MODE_TICKVALUE);
   double tickSize  = MarketInfo(Symbol(), MODE_TICKSIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0)
      return(NormalizeLots(InpFixedLots));

   double riskMoney   = AccountEquity() * InpRiskPercent / 100.0;
   double lossPerLot  = (distance / tickSize) * tickValue;
   if(lossPerLot <= 0.0)
      return(NormalizeLots(InpFixedLots));

   return(NormalizeLots(riskMoney / lossPerLot));
  }

//--- broker minimum distance between price and any stop/limit, in price units
double MinStopDistance()
  {
   double stopLevel   = MarketInfo(Symbol(), MODE_STOPLEVEL);
   double freezeLevel = MarketInfo(Symbol(), MODE_FREEZELEVEL);
   return(MathMax(stopLevel, freezeLevel) * g_pointsToPrice);
  }

//--- where the disaster stop goes: beyond the structural level, never inside
double ProtectiveStop(const int dir, const double structuralLevel)
  {
   if(InpProtectiveSLMode == PSL_NONE)
      return(0.0);

   double pad = 0.0;
   if(InpProtectiveSLMode == PSL_ATR_PCT)
      pad = g_atr5 * InpProtectiveSLATRPct / 100.0;
   else
      pad = InpProtectiveSLPoints * g_pointsToPrice;

   if(pad <= 0.0)
      return(0.0);

   double level = (dir == DIR_LONG) ? structuralLevel - pad
                                    : structuralLevel + pad;
   return(NormalizePrice(level));
  }

bool IsRetryableError(const int code)
  {
   switch(code)
     {
      case ERR_SERVER_BUSY:
      case ERR_NO_CONNECTION:
      case ERR_TRADE_TIMEOUT:
      case ERR_INVALID_PRICE:
      case ERR_PRICE_CHANGED:
      case ERR_OFF_QUOTES:
      case ERR_BROKER_BUSY:
      case ERR_REQUOTE:
      case ERR_TRADE_CONTEXT_BUSY:
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| CSV trade log - feeds the Phase 5 ML loop                        |
//+------------------------------------------------------------------+
void LogRow(const string event, const int slot, const int dir,
            const double price, const double structural, const double target,
            const double lots, const string note)
  {
   if(!InpWriteCSVLog)
      return;

   string file = StringFormat("AsiaBreakout_%s.csv", Symbol());
   int handle = FileOpen(file, FILE_CSV|FILE_READ|FILE_WRITE|FILE_SHARE_READ, ',');
   if(handle == INVALID_HANDLE)
      return;

   if(FileSize(handle) == 0)
      FileWrite(handle, "server_time", "event", "slot", "symbol", "dir",
                "price", "structural_level", "target", "lots", "atr5", "note");

   FileSeek(handle, 0, SEEK_END);
   FileWrite(handle,
             TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS),
             event,
             SlotName(slot),
             Symbol(),
             (dir == DIR_LONG ? "LONG" : (dir == DIR_SHORT ? "SHORT" : "-")),
             DoubleToString(price, Digits),
             DoubleToString(structural, Digits),
             DoubleToString(target, Digits),
             DoubleToString(lots, 2),
             DoubleToString(g_atr5, Digits),
             note);
   FileClose(handle);
  }

//+------------------------------------------------------------------+
//| Open a position                                                  |
//+------------------------------------------------------------------+
bool OpenTrade(const int slot, const int dir,
               const double structuralLevel, const double target)
  {
   RefreshRates();
   double entry = (dir == DIR_LONG) ? Ask : Bid;
   double lots  = ComputeLots(entry, structuralLevel);
   double stop  = ProtectiveStop(dir, structuralLevel);
   double tp    = NormalizePrice(target);
   int    type  = (dir == DIR_LONG) ? OP_BUY : OP_SELL;
   string note  = StringFormat("%s-%s", InpTradeComment, SlotName(slot));

   //--- keep the broker's minimum distance
   double minDist = MinStopDistance();
   if(minDist > 0.0)
     {
      if(dir == DIR_LONG)
        {
         if(tp - entry < minDist)
           {
            PrintFormat("[%s] %s skipped: target %s is inside the broker stop level",
                        InpTradeComment, SlotName(slot), DoubleToString(tp, Digits));
            return(false);
           }
         if(stop > 0.0 && entry - stop < minDist)
            stop = NormalizePrice(entry - minDist);
        }
      else
        {
         if(entry - tp < minDist)
           {
            PrintFormat("[%s] %s skipped: target %s is inside the broker stop level",
                        InpTradeComment, SlotName(slot), DoubleToString(tp, Digits));
            return(false);
           }
         if(stop > 0.0 && stop - entry < minDist)
            stop = NormalizePrice(entry + minDist);
        }
     }

   int ticket = -1;
   for(int attempt = 0; attempt <= InpOrderRetries; attempt++)
     {
      RefreshRates();
      entry = NormalizePrice((dir == DIR_LONG) ? Ask : Bid);

      ticket = OrderSend(Symbol(), type, lots, entry, InpSlippagePoints,
                         stop, tp, note, SlotMagic(slot), 0,
                         (dir == DIR_LONG) ? clrDodgerBlue : clrOrangeRed);
      if(ticket >= 0)
         break;

      int err = GetLastError();

      //--- ECN accounts reject stops sent with a market order. Send naked and
      //--- attach the levels afterwards.
      if(err == ERR_INVALID_STOPS && (stop != 0.0 || tp != 0.0))
        {
         RefreshRates();
         entry = NormalizePrice((dir == DIR_LONG) ? Ask : Bid);
         ticket = OrderSend(Symbol(), type, lots, entry, InpSlippagePoints,
                            0, 0, note, SlotMagic(slot), 0, clrGray);
         if(ticket >= 0)
           {
            if(OrderSelect(ticket, SELECT_BY_TICKET))
              {
               if(!OrderModify(ticket, OrderOpenPrice(), stop, tp, 0, clrGray))
                  PrintFormat("[%s] %s WARNING: naked fill, OrderModify failed (%d). "
                              "No broker stop or target is attached.",
                              InpTradeComment, SlotName(slot), GetLastError());
              }
            break;
           }
         err = GetLastError();
        }

      PrintFormat("[%s] %s OrderSend failed (attempt %d/%d), error %d",
                  InpTradeComment, SlotName(slot), attempt+1, InpOrderRetries+1, err);
      if(!IsRetryableError(err))
         break;
      Sleep(400);
     }

   if(ticket < 0)
     {
      LogRow("ENTRY_FAILED", slot, dir, entry, structuralLevel, tp, lots, "order rejected");
      return(false);
     }

   RememberExitLevel(slot, dir, structuralLevel, ticket);
   g_tradesToday[slot]++;

   PrintFormat("[%s] %s %s opened #%d  lots=%s entry=%s structural=%s TP=%s disasterSL=%s",
               InpTradeComment, SlotName(slot),
               (dir == DIR_LONG ? "LONG" : "SHORT"), ticket,
               DoubleToString(lots, 2), DoubleToString(entry, Digits),
               DoubleToString(structuralLevel, Digits),
               DoubleToString(tp, Digits),
               (stop > 0.0 ? DoubleToString(stop, Digits) : "none"));

   LogRow("ENTRY", slot, dir, entry, structuralLevel, tp, lots,
          StringFormat("ticket=%d", ticket));
   return(true);
  }

//+------------------------------------------------------------------+
//| Close a slot's position                                          |
//+------------------------------------------------------------------+
bool CloseSlot(const int slot, const string reason)
  {
   bool closedSomething = false;

   for(int pass = 0; pass < 8; pass++)
     {
      if(!SelectSlotOrder(slot))
         break;

      int    ticket = OrderTicket();
      double lots   = OrderLots();
      int    type   = OrderType();
      int    dir    = (type == OP_BUY) ? DIR_LONG : DIR_SHORT;

      bool ok = false;
      for(int attempt = 0; attempt <= InpOrderRetries; attempt++)
        {
         RefreshRates();
         double price = (type == OP_BUY) ? Bid : Ask;
         ok = OrderClose(ticket, lots, NormalizePrice(price),
                         InpSlippagePoints, clrGoldenrod);
         if(ok)
            break;

         int err = GetLastError();
         PrintFormat("[%s] %s OrderClose #%d failed (attempt %d/%d), error %d",
                     InpTradeComment, SlotName(slot), ticket,
                     attempt+1, InpOrderRetries+1, err);
         if(!IsRetryableError(err))
            break;
         Sleep(400);
        }

      if(!ok)
        {
         //--- do not go quiet on a position that refuses to close
         Alert(StringFormat("%s %s: FAILED to close #%d (%s). Manual action needed.",
                            InpTradeComment, Symbol(), ticket, reason));
         LogRow("EXIT_FAILED", slot, dir, 0, g_exitLevel[slot], 0, lots, reason);
         return(false);
        }

      closedSomething = true;
      double exitPrice = 0.0;
      double profit    = 0.0;
      if(OrderSelect(ticket, SELECT_BY_TICKET, MODE_HISTORY))
        {
         exitPrice = OrderClosePrice();
         profit    = OrderProfit() + OrderSwap() + OrderCommission();
        }

      PrintFormat("[%s] %s closed #%d (%s) at %s, P/L %s",
                  InpTradeComment, SlotName(slot), ticket, reason,
                  DoubleToString(exitPrice, Digits), DoubleToString(profit, 2));

      LogRow("EXIT", slot, dir, exitPrice, g_exitLevel[slot], 0, lots,
             StringFormat("%s pl=%s", reason, DoubleToString(profit, 2)));

      if(reason == "close-based stop")
         g_lastStopDir[slot] = dir;
      g_openTicket[slot] = 0;
     }

   if(closedSomething)
      ForgetExitLevel(slot);
   return(true);
  }

//--- close everything the EA owns, both slots
void CloseAllSlots(const string reason)
  {
   for(int slot = 0; slot < SLOT_COUNT; slot++)
      if(CountOpen(SlotMagic(slot)) > 0)
         CloseSlot(slot, reason);
  }

//+------------------------------------------------------------------+
//| Reconcile a position the BROKER closed                           |
//|                                                                  |
//| The target is a real TP order, so most winning trades never pass  |
//| through CloseSlot(). Without this the CSV log would only ever     |
//| record losers, which would quietly poison anything downstream     |
//| that learns from it.                                             |
//+------------------------------------------------------------------+
void ReconcileClosed(const int slot)
  {
   if(g_openTicket[slot] <= 0)
      return;
   if(CountOpen(SlotMagic(slot)) > 0)
      return;                                   // still in the market

   int ticket = g_openTicket[slot];
   if(!OrderSelect(ticket, SELECT_BY_TICKET, MODE_HISTORY))
     {
      //--- cannot see it; clear the state rather than act on a stale level
      ForgetExitLevel(slot);
      return;
     }
   if(OrderCloseTime() == 0)
      return;                                   // not actually closed yet

   double exitPrice = OrderClosePrice();
   double profit    = OrderProfit() + OrderSwap() + OrderCommission();
   double tp        = OrderTakeProfit();
   double sl        = OrderStopLoss();
   int    dir       = (OrderType() == OP_BUY) ? DIR_LONG : DIR_SHORT;
   double tolerance = MathMax(g_pointsToPrice * 5, MinStopDistance());

   string reason = "closed externally";
   if(tp > 0.0 && MathAbs(exitPrice - tp) <= tolerance)
      reason = "target touched";
   else if(sl > 0.0 && MathAbs(exitPrice - sl) <= tolerance)
     {
      reason = "disaster stop";
      g_lastStopDir[slot] = dir;
     }

   PrintFormat("[%s] %s #%d closed by the broker (%s) at %s, P/L %s",
               InpTradeComment, SlotName(slot), ticket, reason,
               DoubleToString(exitPrice, Digits), DoubleToString(profit, 2));

   LogRow("EXIT", slot, dir, exitPrice, g_exitLevel[slot], tp, OrderLots(),
          StringFormat("%s pl=%s", reason, DoubleToString(profit, 2)));

   ForgetExitLevel(slot);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  FILTERS                                                         |
//|                                                                  |
//+------------------------------------------------------------------+
bool WeekdayAllowed(const datetime nowBroker)
  {
   MqlDateTime t;
   TimeToStruct(nowBroker, t);
   switch(t.day_of_week)
     {
      case 1: return(InpTradeMon);
      case 2: return(InpTradeTue);
      case 3: return(InpTradeWed);
      case 4: return(InpTradeThu);
      case 5: return(InpTradeFri);
     }
   return(false);   // Saturday / Sunday
  }

bool SpreadAcceptable()
  {
   if(InpMaxSpreadPoints <= 0)
      return(true);
   double spread = (Ask - Bid) / g_pointsToPrice;
   return(spread <= InpMaxSpreadPoints);
  }

//--- everything that can veto an entry before the levels are even consulted
bool GlobalEntryAllowed(const int slot, const datetime nowBroker, string &why)
  {
   if(!SlotEnabled(slot))
     { why = "mode off"; return(false); }

   if(!WeekdayAllowed(nowBroker))
     { why = "weekday off"; return(false); }

   if(g_atr5 <= 0.0)
     { why = "no ATR"; return(false); }

   if(CountOpen(SlotMagic(slot)) > 0)
     { why = "trade open"; return(false); }

   if(InpMode == MODE_BOTH && InpOneTradeAcrossModes && CountOpenAnySlot() > 0)
     { why = "other flavor in market"; return(false); }

   if(g_tradesToday[slot] >= InpMaxTradesPerDay)
     { why = "daily cap"; return(false); }

   if(!SpreadAcceptable())
     { why = "spread"; return(false); }

   datetime hardExit = NextHardExit(nowBroker);
   if(nowBroker + InpNoNewTradesBeforeCloseM*60 >= hardExit)
     { why = "near NY close"; return(false); }

   return(true);
  }

//--- direction-specific vetoes that depend on what already happened today
bool DirectionAllowed(const int slot, const int dir, string &why)
  {
   if(dir == DIR_LONG && !InpTradeLongs)
     { why = "longs off"; return(false); }
   if(dir == DIR_SHORT && !InpTradeShorts)
     { why = "shorts off"; return(false); }

   if(g_lastStopDir[slot] != DIR_NONE)
     {
      if(dir == g_lastStopDir[slot] && !InpAllowReEntryAfterStop)
        { why = "already stopped out this way"; return(false); }
      if(dir != g_lastStopDir[slot] && !InpAllowOppositeSameDay)
        { why = "opposite side blocked after stop"; return(false); }
     }
   return(true);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  SIGNALS                                                         |
//|                                                                  |
//|  Entry is close-based. Called once per closed signal bar.        |
//+------------------------------------------------------------------+
void EvaluateEntry(const int slot, const datetime nowBroker,
                   const datetime barClose)
  {
   string why = "";
   if(!GlobalEntryAllowed(slot, nowBroker, why))
     { g_skipReason[slot] = why; return; }

   double levelHigh, levelLow, stopHigh, stopLow;
   if(!SlotLevels(slot, levelHigh, levelLow, stopHigh, stopLow))
     { g_skipReason[slot] = "levels not ready"; return; }

   //--- the bar must have closed AFTER the level was finalised, otherwise a
   //--- bar from inside the session could be read as a breakout of it
   datetime levelReadyAt = (slot == SLOT_ASIA)
                           ? g_asiaEndB
                           : g_trigOpenB + PeriodSeconds(InpTriggerTF);
   if(barClose <= levelReadyAt)
     { g_skipReason[slot] = "bar predates level"; return; }

   //--- A level stays loaded until the next session replaces it, which means
   //--- that hours after the NY close the previous day's range is still in
   //--- memory. Without this check a bar closing beyond that dead level would
   //--- open a brand new trade on it. Any level formed before the most recent
   //--- hard exit is expired, whatever the daily counters say.
   if(levelReadyAt <= PrevHardExit(nowBroker))
     { g_skipReason[slot] = "level expired at NY close"; return; }

   //--- range-size sanity
   double rangePoints = (levelHigh - levelLow) / g_pointsToPrice;
   if(InpMinRangePoints > 0 && rangePoints < InpMinRangePoints)
     { g_skipReason[slot] = "range too narrow"; return; }
   if(InpMaxRangePoints > 0 && rangePoints > InpMaxRangePoints)
     { g_skipReason[slot] = "range too wide"; return; }

   double close  = iClose(NULL, InpSignalTF, 1);
   double buffer = InpBreakoutBufferPoints * g_pointsToPrice;
   double target = InpTPPctOfATR / 100.0 * g_atr5;

   int    dir        = DIR_NONE;
   double structural = 0.0;
   double tp         = 0.0;

   if(close > levelHigh + buffer)
     {
      dir        = DIR_LONG;
      structural = stopLow;
      tp         = stopLow + target;      // 80% of ATR5 measured from the bottom
     }
   else if(close < levelLow - buffer)
     {
      dir        = DIR_SHORT;
      structural = stopHigh;
      tp         = stopHigh - target;     // 80% of ATR5 measured from the top
     }
   else
     {
      g_skipReason[slot] = "no breakout";
      return;
     }

   if(!DirectionAllowed(slot, dir, why))
     { g_skipReason[slot] = why; return; }

   //--- structural stop distance sanity
   RefreshRates();
   double entry = (dir == DIR_LONG) ? Ask : Bid;
   double slPoints = MathAbs(entry - structural) / g_pointsToPrice;
   if(InpMaxSLPoints > 0 && slPoints > InpMaxSLPoints)
     {
      g_skipReason[slot] = "stop too far";
      PrintFormat("[%s] %s skipped: structural stop is %.0f points away (max %d)",
                  InpTradeComment, SlotName(slot), slPoints, InpMaxSLPoints);
      LogRow("SKIP", slot, dir, entry, structural, tp, 0, "stop distance");
      return;
     }

   //--- THE EDGE CASE. When the range is wider than the ATR-derived target,
   //--- the target sits at or behind the entry. Skip the day, do not fudge it.
   bool targetBehind = (dir == DIR_LONG) ? (tp <= entry) : (tp >= entry);
   if(targetBehind)
     {
      g_skipReason[slot] = "target behind entry";
      PrintFormat("[%s] %s skipped: range %.0f pts exceeds %.0f%% of ATR5 (%.0f pts), "
                  "target %s is behind entry %s",
                  InpTradeComment, SlotName(slot), rangePoints, InpTPPctOfATR,
                  target / g_pointsToPrice,
                  DoubleToString(tp, Digits), DoubleToString(entry, Digits));
      LogRow("SKIP", slot, dir, entry, structural, tp, 0, "target behind entry");
      return;
     }

   OpenTrade(slot, dir, structural, tp);
  }

//+------------------------------------------------------------------+
//| Close-based stop. Called once per closed signal bar.             |
//+------------------------------------------------------------------+
void EvaluateCloseStop(const int slot)
  {
   if(CountOpen(SlotMagic(slot)) == 0)
      return;

   RecallExitLevel(slot);
   if(g_exitLevel[slot] <= 0.0 || g_openDir[slot] == DIR_NONE)
     {
      //--- should not happen; if it does, say so rather than guess a level
      PrintFormat("[%s] %s WARNING: open position with no remembered exit level. "
                  "The close-based stop is inactive; only the disaster stop and "
                  "the NY close will exit it.", InpTradeComment, SlotName(slot));
      return;
     }

   double close = iClose(NULL, InpSignalTF, 1);

   bool stopped = (g_openDir[slot] == DIR_LONG)
                  ? (close < g_exitLevel[slot])
                  : (close > g_exitLevel[slot]);

   if(stopped)
     {
      PrintFormat("[%s] %s close-based stop: bar closed at %s, level %s",
                  InpTradeComment, SlotName(slot),
                  DoubleToString(close, Digits),
                  DoubleToString(g_exitLevel[slot], Digits));
      CloseSlot(slot, "close-based stop");
     }
  }

//+------------------------------------------------------------------+
//| Hard exit at the NY close. Checked on every tick.                |
//+------------------------------------------------------------------+
void EnforceHardExit(const datetime nowBroker)
  {
   datetime lastClose = PrevHardExit(nowBroker);

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      if(!SelectSlotOrder(slot))
         continue;
      //--- a position opened before the most recent NY close has outlived its
      //--- session. This also recovers correctly after a terminal restart.
      if(OrderOpenTime() < lastClose)
         CloseSlot(slot, "NY close");
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  DISPLAY                                                         |
//|                                                                  |
//+------------------------------------------------------------------+
#define OBJ_PREFIX "ABEA_"

void DrawBox(const string name, const datetime t1, const double p1,
             const datetime t2, const double p2, const color clr)
  {
   string id = OBJ_PREFIX + name;
   if(ObjectFind(0, id) < 0)
     {
      ObjectCreate(0, id, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
      ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, id, OBJPROP_STYLE, STYLE_SOLID);
      ObjectSetInteger(0, id, OBJPROP_BACK, true);
      ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
     }
   ObjectMove(0, id, 0, t1, p1);
   ObjectMove(0, id, 1, t2, p2);
  }

void DrawLine(const string name, const datetime t1, const double price,
              const color clr, const int style, const string text)
  {
   string id = OBJ_PREFIX + name;
   if(ObjectFind(0, id) < 0)
     {
      ObjectCreate(0, id, OBJ_TREND, 0, t1, price, TimeCurrent() + PeriodSeconds()*20, price);
      ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, id, OBJPROP_STYLE, style);
      ObjectSetInteger(0, id, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, id, OBJPROP_RAY_RIGHT, false);
      ObjectSetInteger(0, id, OBJPROP_SELECTABLE, false);
     }
   ObjectMove(0, id, 0, t1, price);
   ObjectMove(0, id, 1, TimeCurrent() + PeriodSeconds()*20, price);
   ObjectSetString(0, id, OBJPROP_TEXT, text);
  }

void RedrawObjects()
  {
   if(!InpDrawObjects)
      return;

   if(g_asiaReady)
     {
      DrawBox("asia_box", g_asiaStartB, g_asiaHigh, g_asiaEndB, g_asiaLow, InpColorRange);
      DrawLine("asia_hi", g_asiaEndB, g_asiaHigh, InpColorRange, STYLE_DOT, "Asia High");
      DrawLine("asia_lo", g_asiaEndB, g_asiaLow,  InpColorRange, STYLE_DOT, "Asia Low");
     }

   if(g_trigReady)
     {
      datetime trigEnd = g_trigOpenB + PeriodSeconds(InpTriggerTF);
      DrawBox("trig_box", g_trigOpenB, g_trigHigh, trigEnd, g_trigLow, clrDarkOrange);
      DrawLine("trig_hi", trigEnd, g_trigHigh, clrDarkOrange, STYLE_DOT, "Trigger High");
      DrawLine("trig_lo", trigEnd, g_trigLow,  clrDarkOrange, STYLE_DOT, "Trigger Low");
     }

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      string tag = SlotName(slot);
      if(SelectSlotOrder(slot))
        {
         DrawLine("tp_" + tag, OrderOpenTime(), OrderTakeProfit(),
                  InpColorTP, STYLE_SOLID, tag + " target (touch)");
         if(g_exitLevel[slot] > 0.0)
            DrawLine("sl_" + tag, OrderOpenTime(), g_exitLevel[slot],
                     InpColorSL, STYLE_SOLID, tag + " stop (close)");
        }
      else
        {
         ObjectDelete(0, OBJ_PREFIX + "tp_" + tag);
         ObjectDelete(0, OBJ_PREFIX + "sl_" + tag);
        }
     }
  }

void UpdatePanel(const datetime nowBroker)
  {
   if(!InpShowPanel)
     {
      Comment("");
      return;
     }

   string modeText = (InpMode == MODE_ASIA_RANGE)     ? "Asia range"
                   : (InpMode == MODE_TRIGGER_CANDLE) ? "Trigger candle"
                                                      : "Both";

   string text = StringFormat("%s  %s  [%s]\n", InpTradeComment, Symbol(), modeText);
   text += StringFormat("Server %s   UTC %s   offset %+.1fh\n",
                        TimeToString(nowBroker, TIME_MINUTES),
                        TimeToString(BrokerToUtc(nowBroker), TIME_MINUTES),
                        BrokerOffsetAtUtc(BrokerToUtc(nowBroker)) / 3600.0);
   text += StringFormat("ATR%d = %s  (%.0f pts)   target %.0f%% = %.0f pts\n",
                        InpATRDays, DoubleToString(g_atr5, Digits),
                        g_atr5 / g_pointsToPrice, InpTPPctOfATR,
                        g_atr5 * InpTPPctOfATR / 100.0 / g_pointsToPrice);

   if(g_asiaReady)
      text += StringFormat("Asia  %s - %s   H %s  L %s  (%.0f pts)\n",
                           TimeToString(g_asiaStartB, TIME_MINUTES),
                           TimeToString(g_asiaEndB, TIME_MINUTES),
                           DoubleToString(g_asiaHigh, Digits),
                           DoubleToString(g_asiaLow, Digits),
                           (g_asiaHigh - g_asiaLow) / g_pointsToPrice);
   else
      text += "Asia  building...\n";

   if(SlotEnabled(SLOT_TRIGGER) || InpCandleSLSource == CSL_ASIA_SESSION)
     {
      if(g_trigReady)
         text += StringFormat("Trig  %s   H %s  L %s  (%.0f pts)\n",
                              TimeToString(g_trigOpenB, TIME_MINUTES),
                              DoubleToString(g_trigHigh, Digits),
                              DoubleToString(g_trigLow, Digits),
                              (g_trigHigh - g_trigLow) / g_pointsToPrice);
      else
         text += "Trig  waiting...\n";
     }

   text += StringFormat("Hard exit at %s server\n",
                        TimeToString(NextHardExit(nowBroker), TIME_DATE|TIME_MINUTES));

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      if(!SlotEnabled(slot))
         continue;
      string line = StringFormat("%-6s trades %d/%d", SlotName(slot),
                                 g_tradesToday[slot], InpMaxTradesPerDay);
      if(SelectSlotOrder(slot))
         line += StringFormat("   OPEN %s  stop-on-close %s  TP %s",
                              (OrderType() == OP_BUY ? "LONG" : "SHORT"),
                              DoubleToString(g_exitLevel[slot], Digits),
                              DoubleToString(OrderTakeProfit(), Digits));
      else if(StringLen(g_skipReason[slot]) > 0)
         line += "   idle: " + g_skipReason[slot];
      text += line + "\n";
     }

   Comment(text);
  }

void ClearObjects()
  {
   for(int i = ObjectsTotal(0) - 1; i >= 0; i--)
     {
      string name = ObjectName(0, i);
      if(StringFind(name, OBJ_PREFIX) == 0)
         ObjectDelete(0, name);
     }
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  DAY ROLLOVER                                                    |
//|                                                                  |
//|  The trading day is the broker's calendar day. On the usual       |
//|  UTC+2/UTC+3 server clock that boundary IS the New York close, so |
//|  the daily counters reset exactly when the session ends.          |
//+------------------------------------------------------------------+
void RollDay(const datetime nowBroker)
  {
   datetime today = nowBroker - (nowBroker % 86400);
   if(today == g_dayKey)
      return;

   g_dayKey = today;
   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      g_tradesToday[slot] = 0;
      g_lastStopDir[slot] = DIR_NONE;
      g_skipReason[slot]  = "";
     }

   g_atr5   = ComputeATR();
   g_atrDay = today;
   PrintFormat("[%s] New trading day %s   ATR%d = %s (%.0f pts)",
               InpTradeComment, TimeToString(today, TIME_DATE),
               InpATRDays, DoubleToString(g_atr5, Digits),
               g_atr5 / g_pointsToPrice);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  LIFECYCLE                                                       |
//|                                                                  |
//+------------------------------------------------------------------+
bool ValidateInputs()
  {
   bool ok = true;

   if(InpTPPctOfATR <= 0.0)
     { Print("InpTPPctOfATR must be greater than zero."); ok = false; }
   if(InpATRDays < 1)
     { Print("InpATRDays must be at least 1."); ok = false; }
   if(InpAsiaStartHour < 0 || InpAsiaStartHour > 23 || InpAsiaEndHour < 0 || InpAsiaEndHour > 23)
     { Print("Asia session hours must be 0..23."); ok = false; }
   if(InpAsiaStartHour == InpAsiaEndHour && InpAsiaStartMin == InpAsiaEndMin)
     { Print("Asia session start and end are the same instant."); ok = false; }
   if(InpTriggerHour < 0 || InpTriggerHour > 23)
     { Print("Trigger hour must be 0..23."); ok = false; }
   if(InpMaxTradesPerDay < 1)
     { Print("InpMaxTradesPerDay must be at least 1."); ok = false; }
   if(InpMagicAsia == InpMagicTrigger)
     { Print("The two magic numbers must differ."); ok = false; }
   if(!InpTradeLongs && !InpTradeShorts)
     { Print("Both directions are disabled - the EA would never trade."); ok = false; }

   //--- the trigger candle must be able to exist on the trigger timeframe
   int trigBarMinutes = PeriodSeconds(InpTriggerTF) / 60;
   if(trigBarMinutes > 0 && trigBarMinutes < 1440)
     {
      int minuteOfDay = InpTriggerHour*60 + InpTriggerMin;
      if(minuteOfDay % trigBarMinutes != 0)
         PrintFormat("WARNING: %02d:%02d does not fall on a %d-minute bar boundary. "
                     "No trigger candle will be found.",
                     InpTriggerHour, InpTriggerMin, trigBarMinutes);
     }

   if(InpProtectiveSLMode == PSL_NONE)
      Print("WARNING: no broker stop will be attached. If this terminal or the "
            "VPS goes down with a position open, nothing limits the loss.");

   return(ok);
  }

void ResolveBrokerClock()
  {
   if(InpBrokerOffsetMode == BOFF_MANUAL || IsTesting())
     {
      g_brokerWinterOffsetSec = InpBrokerWinterOffsetHours * 3600;
      if(IsTesting() && InpBrokerOffsetMode == BOFF_AUTO)
         Print("Strategy Tester: TimeGMT() is not meaningful here, so the manual "
               "winter offset is used. Make sure InpBrokerWinterOffsetHours is right.");
     }
   else
     {
      datetime utcNow = TimeGMT();
      int currentOffset = (int)MathRound((double)(TimeCurrent() - utcNow) / 3600.0) * 3600;
      //--- strip today's DST so the stored value is the WINTER base, which is
      //--- what the conversion helpers expect
      if(DstActive(InpBrokerDSTRule, utcNow))
         currentOffset -= 3600;
      g_brokerWinterOffsetSec = currentOffset;
     }

   PrintFormat("[%s] Broker winter offset resolved to UTC%+.0f (DST rule: %s). "
               "Right now the server is UTC%+.1f.",
               InpTradeComment, g_brokerWinterOffsetSec / 3600.0,
               (InpBrokerDSTRule == DST_US ? "US" : (InpBrokerDSTRule == DST_EU ? "EU" : "none")),
               BrokerOffsetAtUtc(BrokerToUtc(TimeCurrent())) / 3600.0);
  }

int OnInit()
  {
   if(!ValidateInputs())
      return(INIT_PARAMETERS_INCORRECT);

   g_pointsToPrice   = Point;
   g_stopLevelPoints = (int)MarketInfo(Symbol(), MODE_STOPLEVEL);
   PrintFormat("[%s] %s: digits=%d point=%s broker stop level=%d points",
               InpTradeComment, Symbol(), Digits,
               DoubleToString(g_pointsToPrice, 8), g_stopLevelPoints);

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      g_tradesToday[slot]   = 0;
      g_lastStopDir[slot]   = DIR_NONE;
      g_lastSignalBar[slot] = iTime(NULL, InpSignalTF, 0);
      g_exitLevel[slot]     = 0.0;
      g_openDir[slot]       = DIR_NONE;
      g_openTicket[slot]    = 0;
      g_skipReason[slot]    = "";
      RecallExitLevel(slot);          // survive a restart with a position open
     }

   ResolveBrokerClock();

   g_dayKey = 0;
   RollDay(TimeCurrent());

   datetime nowBroker = TimeCurrent();
   UpdateAsiaRange(nowBroker);
   if(SlotEnabled(SLOT_TRIGGER))
      UpdateTriggerCandle(nowBroker);

   PrintFormat("[%s] Ready on %s. Entry: CLOSE beyond level. Stop: CLOSE back "
               "beyond level. Target: TOUCH at %.0f%% of ATR%d from the level. "
               "Hard exit: %s server time.",
               InpTradeComment, Symbol(), InpTPPctOfATR, InpATRDays,
               TimeToString(NextHardExit(nowBroker), TIME_DATE|TIME_MINUTES));

   return(INIT_SUCCEEDED);
  }

void OnDeinit(const int reason)
  {
   ClearObjects();
   Comment("");
  }

void OnTick()
  {
   datetime nowBroker = TimeCurrent();

   RollDay(nowBroker);

   //--- levels first; the Asia range is always maintained because the candle
   //--- flavor can be configured to stop against it
   UpdateAsiaRange(nowBroker);
   if(SlotEnabled(SLOT_TRIGGER))
      UpdateTriggerCandle(nowBroker);

   //--- pick up anything the broker closed behind our back (TP touch)
   for(int i = 0; i < SLOT_COUNT; i++)
      ReconcileClosed(i);

   //--- the hard exit outranks everything and is checked on every tick
   if(IsTradeAllowed())
      EnforceHardExit(nowBroker);

   //--- close-based work happens once per closed signal bar
   datetime currentBar = iTime(NULL, InpSignalTF, 0);
   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      if(!SlotEnabled(slot))
         continue;
      if(currentBar == g_lastSignalBar[slot])
         continue;
      if(!IsTradeAllowed())
         continue;

      g_lastSignalBar[slot] = currentBar;

      //--- exits before entries, so a bar that both stops a trade out and
      //--- breaks the other way is handled in the right order
      EvaluateCloseStop(slot);
      EvaluateEntry(slot, nowBroker,
                    iTime(NULL, InpSignalTF, 1) + PeriodSeconds(InpSignalTF));
     }

   RedrawObjects();
   UpdatePanel(nowBroker);
  }
//+------------------------------------------------------------------+
