//+------------------------------------------------------------------+
//|                                        AsiaBreakout_EA_v2.mq4    |
//|            Asia Session / Trigger Candle breakout Expert Advisor |
//|            v2 - split timeframes, scaled exits, repeat entries   |
//+------------------------------------------------------------------+
//
//  WHAT THIS IS
//    One EA that trades two related breakout patterns on a single pair.
//
//      MODE_ASIA_RANGE     Levels are the high/low of the Asia session.
//      MODE_TRIGGER_CANDLE Levels are the high/low of ONE nominated candle.
//      MODE_BOTH           Both, on separate magic numbers.
//
//  TWO TIMEFRAMES
//    InpEntryTF     ONE candle size does all three jobs: it measures the Asia
//                   high and low, its CLOSE beyond the range is the entry,
//                   and its CLOSE back beyond the level is the stop. The
//                   first such candle to close beyond the range is the trade.
//    InpTriggerTF   the candle whose high/low become the levels in
//                   trigger-candle mode. Nothing else uses it.
//
//    Earlier versions split the measuring timeframe from the breakout
//    timeframe. That was a mistake in practice: you would watch M15 boxes
//    while entries fired on H1 closes, and the entries looked arbitrary.
//    Measuring on a finer timeframe was buying nothing anyway - when the
//    session boundaries land on candle boundaries the high and low of a
//    window are the same whether you read them from M5 or H1 candles, since
//    an H1 high IS the highest of its M15 highs.
//
//  THE SIGNAL RULES - deliberately NOT symmetrical
//
//    ENTRY   a bar on InpEntryTF must CLOSE beyond the level.
//    STOP    a bar on InpEntryTF must CLOSE back beyond the opposite level.
//    TARGET  TOUCH. Price only has to trade there.
//
//  THE EXIT IS IN TWO PARTS (new in v2)
//
//    Part 1  at the ATR target, on TOUCH, close InpPartialClosePct of the
//            position. Default 50%.
//    Part 2  the remainder runs to the New York close and is closed there.
//
//    The close-based stop still governs the runner. If a bar closes back
//    beyond the structural level after the partial has been taken, the
//    remainder is closed there rather than at the NY close.
//
//    Because a broker take-profit closes a WHOLE position, a scaled exit
//    cannot be a resting TP order. When InpPartialClosePct is below 100 the
//    EA watches the target itself, tick by tick, and closes the slice. The
//    disaster stop stays broker-side either way. At exactly 100 the target
//    goes back to being a real TP order, since nothing needs slicing.
//
//  REPEAT ENTRIES (new in v2)
//    InpMaxTradesPerDay entries per flavor per day, default 4, and at most
//    InpMaxOpenPerDirection open at once in each direction, default 1. So a
//    long and a short can be live together, but never two longs.
//
//    A consequence worth understanding: while a runner is still open, that
//    direction is full, so the next long cannot start until the previous one
//    has finished. With scaled exits the runner usually lives until the NY
//    close, which in practice caps most days at one trade per direction.
//    Set InpPartialClosePct to 100 to have targets free the slot again.
//
//    InpRequireReset (default off) additionally demands that price closes
//    back INSIDE the range before that direction can trigger again. Without
//    it, four consecutive closes beyond the level are four valid signals.
//
//  DAYLIGHT SAVING
//    Every session carries its own timezone with real DST rules. See the
//    TIME section. research/verify_session_clock.py asserts the arithmetic.
//
//  SIGNAL TIMING
//    Everything close-based reads CLOSED bars only (shift >= 1). A signal
//    that appears cannot later vanish.
//
//+------------------------------------------------------------------+
#property copyright "algo-trading-system"
#property link      "https://github.com/mesan4net-blip/algo-trading-system"
#property version   "2.00"
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
   DST_US   = 1,  // Broker follows US/New York DST
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
   PSL_NONE       = 0,  // No broker stop at all
   PSL_ATR_PCT    = 1,  // Percent of ATR5 beyond the structural level
   PSL_POINTS     = 2,  // Fixed points beyond the structural level
   PSL_STRUCT_PCT = 3   // Percent of the ENTRY-to-LEVEL distance beyond it
  };

enum ENUM_STOP_STYLE
  {
   STOP_ON_CLOSE = 0,  // Exit when a signal bar CLOSES beyond the level
   STOP_ON_TOUCH = 1   // Broker stop sits AT the level and fills on a touch
  };

#define DIR_NONE   0
#define DIR_LONG   1
#define DIR_SHORT -1

//--- array index for a direction: 0 long, 1 short
#define DX_LONG    0
#define DX_SHORT   1
#define DX_COUNT   2

#define SLOT_ASIA    0
#define SLOT_TRIGGER 1
#define SLOT_COUNT   2

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input string          _s01                       = "=== STRATEGY ===";          // .
input ENUM_STRAT_MODE InpMode                    = MODE_ASIA_RANGE;             // Which breakout to trade
input double          InpTPPctOfATR              = 80.0;                        // Target as % of 5-day ATR
input ENUM_STOP_STYLE InpStopStyle               = STOP_ON_CLOSE;               // How the structural stop is honoured
input bool            InpTradeLongs              = true;                        // Allow long breakouts
input bool            InpTradeShorts             = true;                        // Allow short breakouts

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

input string          _s06                       = "=== 5-DAY ATR ===";         // .
input int             InpATRDays                 = 5;                           // ATR lookback in daily bars
input bool            InpATRSkipSunday           = true;                        // Skip the broker's stunted Sunday bar

input string          _s07                       = "=== ENTRY FILTERS ===";     // .
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

input string          _s08                       = "=== TRADE CONTROL ===";     // .
input int             InpMaxTradesPerDay         = 4;                           // Max entries per flavor per day
input int             InpMaxOpenPerDirection     = 1;                           // Max positions open at once, per direction
input bool            InpRequireReset            = false;                       // Price must re-enter the range before re-arming
input bool            InpOneTradeAcrossModes     = true;                        // In MODE_BOTH, only one flavor in the market

input string          _s09                       = "=== RISK ===";              // .
input ENUM_LOT_MODE   InpLotMode                 = LOT_FIXED;                   // Position sizing method
input double          InpFixedLots               = 0.10;                        // Fixed lot size
input double          InpRiskPercent             = 1.0;                         // Risk % of equity (structural stop distance)
input ENUM_PSL_MODE   InpProtectiveSLMode        = PSL_ATR_PCT;                 // Disaster stop placed with the order
input double          InpProtectiveSLATRPct      = 25.0;                        // Disaster stop: % of ATR5 beyond level
input int             InpProtectiveSLPoints      = 300;                         // Disaster stop: points beyond level
input double          InpProtectiveSLStructPct   = 50.0;                        // Disaster stop: % of the entry-to-level distance

input string          _s10                       = "=== HARD EXIT (NY CLOSE) ==="; // .
input ENUM_TZ         InpNYCloseTZ               = TZ_NEWYORK;                  // Timezone the NY close is given in
input int             InpNYCloseHour             = 17;                          // NY close hour
input int             InpNYCloseMin              = 0;                           // NY close minute
input bool            InpFridayEarlyClose        = false;                       // Use a different close time on Friday
input int             InpFridayCloseHour         = 16;                          // Friday close hour
input int             InpFridayCloseMin          = 0;                           // Friday close minute

input string          _s11                       = "=== BROKER CLOCK ===";      // .
input ENUM_OFFSET_MODE InpBrokerOffsetMode       = BOFF_AUTO;                   // How to learn the server GMT offset
input int             InpBrokerWinterOffsetHours = 2;                           // Server offset from UTC in WINTER
input ENUM_DST_RULE   InpBrokerDSTRule           = DST_US;                      // Does the server clock shift, and how

input string          _s12                       = "=== EXECUTION ===";         // .
input int             InpSlippagePoints          = 5;                           // Max slippage (points)
input int             InpOrderRetries            = 3;                           // Retries on a failed order
input int             InpMagicAsia               = 8801;                        // Magic number, Asia range flavor
input int             InpMagicTrigger            = 8802;                        // Magic number, trigger candle flavor
input string          InpTradeComment            = "AsiaBO";                    // Order comment prefix

input string          _s13                       = "=== DISPLAY / LOG ===";     // .
input bool            InpDrawObjects             = true;                        // Draw levels and boxes on the chart
input bool            InpShowPanel               = true;                        // Show the status panel
input bool            InpWriteCSVLog             = true;                        // Write a CSV trade log
input color           InpColorRange              = clrSteelBlue;                // Range box colour
input color           InpColorTP                 = clrSeaGreen;                 // Target line colour
input color           InpColorSL                 = clrFireBrick;                // Stop line colour

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
int      g_brokerWinterOffsetSec = 0;
double   g_pointsToPrice         = 0.0;
int      g_stopLevelPoints       = 0;

datetime g_dayKey                = 0;
double   g_atr5                  = 0.0;

bool     g_asiaReady   = false;
double   g_asiaHigh    = 0.0;
double   g_asiaLow     = 0.0;
datetime g_asiaStartB  = 0;
datetime g_asiaEndB    = 0;

bool     g_trigReady   = false;
double   g_trigHigh    = 0.0;
double   g_trigLow     = 0.0;
datetime g_trigOpenB   = 0;

//--- per flavor
int      g_tradesToday[SLOT_COUNT];
datetime g_lastSignalBar[SLOT_COUNT];
string   g_skipReason[SLOT_COUNT];

//--- per flavor AND direction. A long and a short are independent trades
//--- with independent stops, targets and partial-fill state.
int      g_ticket[SLOT_COUNT][DX_COUNT];
double   g_exitLevel[SLOT_COUNT][DX_COUNT];
double   g_target[SLOT_COUNT][DX_COUNT];
double   g_entryPrice[SLOT_COUNT][DX_COUNT];
bool     g_partialDone[SLOT_COUNT][DX_COUNT];
bool     g_fullAtTarget[SLOT_COUNT][DX_COUNT];
bool     g_armed[SLOT_COUNT][DX_COUNT];

//--- resolved from InpMaxOpenPerDirection, clamped to what the per-direction
//--- state above can actually track: one ticket, one stop, one target
int      g_maxOpenPerDir = 1;
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
   if(!RangeInWindow(InpEntryTF, startB, endB, high, low))
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
//|  SLOT AND DIRECTION HELPERS                                      |
//|                                                                  |
//|  v2 tracks state per FLAVOR and per DIRECTION. A long and a short |
//|  of the same flavor are separate trades with their own stop,      |
//|  target and partial-fill state, and they can be open together.    |
//+------------------------------------------------------------------+
int SlotMagic(const int slot)
  {
   return(slot == SLOT_ASIA ? InpMagicAsia : InpMagicTrigger);
  }

string SlotName(const int slot)
  {
   return(slot == SLOT_ASIA ? "ASIA" : "CANDLE");
  }

int DirIndex(const int dir)
  {
   return(dir == DIR_LONG ? DX_LONG : DX_SHORT);
  }

int DirOf(const int dx)
  {
   return(dx == DX_LONG ? DIR_LONG : DIR_SHORT);
  }

string DirName(const int dir)
  {
   return(dir == DIR_LONG ? "LONG" : "SHORT");
  }

bool SlotEnabled(const int slot)
  {
   if(InpMode == MODE_BOTH)
      return(true);
   if(slot == SLOT_ASIA)
      return(InpMode == MODE_ASIA_RANGE);
   return(InpMode == MODE_TRIGGER_CANDLE);
  }

//--- 'high'/'low' are the breakout levels, 'stopHigh'/'stopLow' the stop and
//--- target anchors
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

//+------------------------------------------------------------------+
//| State that must survive a restart                                |
//+------------------------------------------------------------------+
string GVName(const int slot, const int dx, const string field)
  {
   return(StringFormat("ABEA2_%s_%d_%s_%s", Symbol(), SlotMagic(slot),
                       (dx == DX_LONG ? "L" : "S"), field));
  }

void RememberTrade(const int slot, const int dx, const int ticket,
                   const double exitLevel, const double target,
                   const double entry, const bool fullAtTarget)
  {
   g_ticket[slot][dx]       = ticket;
   g_exitLevel[slot][dx]    = exitLevel;
   g_target[slot][dx]       = target;
   g_entryPrice[slot][dx]   = entry;
   g_partialDone[slot][dx]  = false;
   g_fullAtTarget[slot][dx] = fullAtTarget;

   GlobalVariableSet(GVName(slot, dx, "TICKET"), (double)ticket);
   GlobalVariableSet(GVName(slot, dx, "EXIT"),   exitLevel);
   GlobalVariableSet(GVName(slot, dx, "TGT"),    target);
   GlobalVariableSet(GVName(slot, dx, "ENTRY"),  entry);
   GlobalVariableSet(GVName(slot, dx, "PART"),   0.0);
   GlobalVariableSet(GVName(slot, dx, "FULL"),   fullAtTarget ? 1.0 : 0.0);
  }

void UpdateTradeState(const int slot, const int dx)
  {
   GlobalVariableSet(GVName(slot, dx, "TICKET"), (double)g_ticket[slot][dx]);
   GlobalVariableSet(GVName(slot, dx, "EXIT"),   g_exitLevel[slot][dx]);
   GlobalVariableSet(GVName(slot, dx, "PART"),   g_partialDone[slot][dx] ? 1.0 : 0.0);
  }

void ForgetTrade(const int slot, const int dx)
  {
   g_ticket[slot][dx]       = 0;
   g_exitLevel[slot][dx]    = 0.0;
   g_target[slot][dx]       = 0.0;
   g_entryPrice[slot][dx]   = 0.0;
   g_partialDone[slot][dx]  = false;
   g_fullAtTarget[slot][dx] = false;

   GlobalVariableDel(GVName(slot, dx, "TICKET"));
   GlobalVariableDel(GVName(slot, dx, "EXIT"));
   GlobalVariableDel(GVName(slot, dx, "TGT"));
   GlobalVariableDel(GVName(slot, dx, "ENTRY"));
   GlobalVariableDel(GVName(slot, dx, "PART"));
   GlobalVariableDel(GVName(slot, dx, "FULL"));
  }

void RecallTrade(const int slot, const int dx)
  {
   if(g_ticket[slot][dx] != 0)
      return;
   if(!GlobalVariableCheck(GVName(slot, dx, "TICKET")))
      return;

   g_ticket[slot][dx]       = (int)GlobalVariableGet(GVName(slot, dx, "TICKET"));
   g_exitLevel[slot][dx]    = GlobalVariableGet(GVName(slot, dx, "EXIT"));
   g_target[slot][dx]       = GlobalVariableGet(GVName(slot, dx, "TGT"));
   g_entryPrice[slot][dx]   = GlobalVariableGet(GVName(slot, dx, "ENTRY"));
   g_partialDone[slot][dx]  = (GlobalVariableGet(GVName(slot, dx, "PART")) > 0.5);
   g_fullAtTarget[slot][dx] = (GlobalVariableGet(GVName(slot, dx, "FULL")) > 0.5);
  }

//+------------------------------------------------------------------+
//| Order lookups                                                    |
//+------------------------------------------------------------------+
int CountOpen(const int magic, const int wantType)
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
      if(wantType >= 0 && OrderType() != wantType)
         continue;
      count++;
     }
   return(count);
  }

int CountOpenDir(const int slot, const int dir)
  {
   return(CountOpen(SlotMagic(slot), (dir == DIR_LONG) ? OP_BUY : OP_SELL));
  }

int CountOpenAnySlot()
  {
   return(CountOpen(InpMagicAsia, -1) + CountOpen(InpMagicTrigger, -1));
  }

//--- select this flavor's open position in this direction, if there is one
bool SelectDirOrder(const int slot, const int dir)
  {
   int magic = SlotMagic(slot);
   int want  = (dir == DIR_LONG) ? OP_BUY : OP_SELL;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      if(!OrderSelect(i, SELECT_BY_POS, MODE_TRADES))
         continue;
      if(OrderSymbol() != Symbol() || OrderMagicNumber() != magic)
         continue;
      if(OrderType() == want)
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
double ProtectiveStop(const int dir, const double structuralLevel, const double entry)
  {
   //--- STOP_ON_TOUCH means the broker stop IS the structural stop: it sits
   //--- exactly on the level and fills the moment price trades there. There
   //--- is no pad and no close-based rule.
   if(InpStopStyle == STOP_ON_TOUCH)
      return(NormalizePrice(structuralLevel));

   if(InpProtectiveSLMode == PSL_NONE)
      return(0.0);

   double pad = 0.0;
   if(InpProtectiveSLMode == PSL_ATR_PCT)
      pad = g_atr5 * InpProtectiveSLATRPct / 100.0;
   else if(InpProtectiveSLMode == PSL_STRUCT_PCT)
      //--- scales with the trade's own risk, so a one-candle trigger stop
      //--- does not get an ATR-sized pad slapped underneath it
      pad = MathAbs(entry - structuralLevel) * InpProtectiveSLStructPct / 100.0;
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
             event, SlotName(slot), Symbol(),
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
//|                                                                  |
//|  OPENING A TRADE                                                 |
//|                                                                  |
//+------------------------------------------------------------------+

//--- can this lot size be split into a partial and a runner that both clear
//--- the broker's minimum? If not, the target has to close the whole thing.
bool PartialIsPossible(const double lots, double &partialLots)
  {
   partialLots = 0.0;
   if(InpPartialClosePct <= 0.0 || InpPartialClosePct >= 100.0)
      return(false);

   double minLot = MarketInfo(Symbol(), MODE_MINLOT);
   partialLots = NormalizeLots(lots * InpPartialClosePct / 100.0);
   double runner = NormalizeDouble(lots - partialLots, 2);

   return(partialLots >= minLot && runner >= minLot);
  }

bool OpenTrade(const int slot, const int dir,
               const double structuralLevel, const double target)
  {
   int dx = DirIndex(dir);

   RefreshRates();
   double entry = (dir == DIR_LONG) ? Ask : Bid;
   double lots  = ComputeLots(entry, structuralLevel);
   double stop  = ProtectiveStop(dir, structuralLevel, entry);
   double tp    = NormalizePrice(target);
   int    type  = (dir == DIR_LONG) ? OP_BUY : OP_SELL;
   string note  = StringFormat("%s-%s", InpTradeComment, SlotName(slot));

   //--- decide up front how the target will be taken
   double partialLots = 0.0;
   bool   canSplit    = PartialIsPossible(lots, partialLots);
   bool   noTarget    = (InpPartialClosePct <= 0.0);
   bool   fullAtTarget = false;

   if(noTarget)
     {
      fullAtTarget = false;    // nothing happens at the target at all
     }
   else if(InpPartialClosePct >= 100.0)
     {
      fullAtTarget = true;     // the whole position, so a real TP order works
     }
   else if(!canSplit)
     {
      fullAtTarget = true;
      PrintFormat("[%s] %s %s: %s lots cannot be split %.0f/%.0f above the %s "
                  "minimum, so the TARGET WILL CLOSE THE WHOLE POSITION. "
                  "Raise the lot size to at least twice the minimum for a "
                  "scaled exit.",
                  InpTradeComment, SlotName(slot), DirName(dir),
                  DoubleToString(lots, 2), InpPartialClosePct,
                  100.0 - InpPartialClosePct,
                  DoubleToString(MarketInfo(Symbol(), MODE_MINLOT), 2));
     }

   //--- a resting TP order closes everything, so it is only usable when the
   //--- whole position is meant to go at the target
   double sendTP = fullAtTarget ? tp : 0.0;

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
           {
            if(InpStopStyle == STOP_ON_TOUCH)
               PrintFormat("[%s] %s %s: the level %s is inside the broker's "
                           "minimum stop distance, so the stop is being pushed "
                           "out to %s. The trade risks %.0f points more than the "
                           "level implies.",
                           InpTradeComment, SlotName(slot), DirName(dir),
                           DoubleToString(stop, Digits),
                           DoubleToString(entry - minDist, Digits),
                           (minDist - (entry - stop)) / g_pointsToPrice);
            stop = NormalizePrice(entry - minDist);
           }
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
           {
            if(InpStopStyle == STOP_ON_TOUCH)
               PrintFormat("[%s] %s %s: the level %s is inside the broker's "
                           "minimum stop distance, so the stop is being pushed "
                           "out to %s. The trade risks %.0f points more than the "
                           "level implies.",
                           InpTradeComment, SlotName(slot), DirName(dir),
                           DoubleToString(stop, Digits),
                           DoubleToString(entry + minDist, Digits),
                           (minDist - (stop - entry)) / g_pointsToPrice);
            stop = NormalizePrice(entry + minDist);
           }
        }
     }

   int ticket = -1;
   for(int attempt = 0; attempt <= InpOrderRetries; attempt++)
     {
      RefreshRates();
      entry = NormalizePrice((dir == DIR_LONG) ? Ask : Bid);

      ticket = OrderSend(Symbol(), type, lots, entry, InpSlippagePoints,
                         stop, sendTP, note, SlotMagic(slot), 0,
                         (dir == DIR_LONG) ? clrDodgerBlue : clrOrangeRed);
      if(ticket >= 0)
         break;

      int err = GetLastError();

      //--- ECN accounts reject stops sent with a market order
      if(err == ERR_INVALID_STOPS && (stop != 0.0 || sendTP != 0.0))
        {
         RefreshRates();
         entry = NormalizePrice((dir == DIR_LONG) ? Ask : Bid);
         ticket = OrderSend(Symbol(), type, lots, entry, InpSlippagePoints,
                            0, 0, note, SlotMagic(slot), 0, clrGray);
         if(ticket >= 0)
           {
            if(OrderSelect(ticket, SELECT_BY_TICKET))
               if(!OrderModify(ticket, OrderOpenPrice(), stop, sendTP, 0, clrGray))
                  PrintFormat("[%s] %s WARNING: naked fill, OrderModify failed (%d).",
                              InpTradeComment, SlotName(slot), GetLastError());
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

   RememberTrade(slot, dx, ticket, structuralLevel, tp, entry, fullAtTarget);
   g_tradesToday[slot]++;
   g_armed[slot][dx] = false;

   string plan = noTarget
                 ? "no target, runs to the NY close"
                 : (fullAtTarget
                    ? "whole position at the target"
                    : StringFormat("%.0f%% at the target, rest to the NY close",
                                   InpPartialClosePct));

   string stopStory = (InpStopStyle == STOP_ON_TOUCH)
                      ? StringFormat("stop ON TOUCH at %s (broker holds it)",
                                     DoubleToString(stop, Digits))
                      : StringFormat("stop ON CLOSE at %s (EA holds it) | "
                                     "broker S/L is the DISASTER stop at %s, "
                                     "%.0f points further out - it is NOT the "
                                     "structural stop",
                                     DoubleToString(structuralLevel, Digits),
                                     (stop > 0.0 ? DoubleToString(stop, Digits) : "none"),
                                     (stop > 0.0 ? MathAbs(structuralLevel - stop) / g_pointsToPrice : 0.0));

   PrintFormat("[%s] %s %s opened #%d  lots=%s entry=%s target=%s | %s | %s",
               InpTradeComment, SlotName(slot), DirName(dir), ticket,
               DoubleToString(lots, 2), DoubleToString(entry, Digits),
               DoubleToString(tp, Digits), stopStory, plan);

   LogRow("ENTRY", slot, dir, entry, structuralLevel, tp, lots,
          StringFormat("ticket=%d %s", ticket, plan));
   return(true);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  CLOSING                                                         |
//|                                                                  |
//+------------------------------------------------------------------+

//--- close every open position of one flavor in one direction
bool CloseDir(const int slot, const int dir, const string reason)
  {
   int  dx = DirIndex(dir);
   bool closedSomething = false;

   for(int pass = 0; pass < 8; pass++)
     {
      if(!SelectDirOrder(slot, dir))
         break;

      int    ticket = OrderTicket();
      double lots   = OrderLots();
      int    type   = OrderType();

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
         PrintFormat("[%s] %s %s OrderClose #%d failed (attempt %d/%d), error %d",
                     InpTradeComment, SlotName(slot), DirName(dir), ticket,
                     attempt+1, InpOrderRetries+1, err);
         if(!IsRetryableError(err))
            break;
         Sleep(400);
        }

      if(!ok)
        {
         Alert(StringFormat("%s %s: FAILED to close #%d (%s). Manual action needed.",
                            InpTradeComment, Symbol(), ticket, reason));
         LogRow("EXIT_FAILED", slot, dir, 0, g_exitLevel[slot][dx], 0, lots, reason);
         return(false);
        }

      closedSomething = true;

      double exitPrice = 0.0, profit = 0.0;
      if(OrderSelect(ticket, SELECT_BY_TICKET, MODE_HISTORY))
        {
         exitPrice = OrderClosePrice();
         profit    = OrderProfit() + OrderSwap() + OrderCommission();
        }

      PrintFormat("[%s] %s %s closed #%d (%s) at %s, P/L %s",
                  InpTradeComment, SlotName(slot), DirName(dir), ticket, reason,
                  DoubleToString(exitPrice, Digits), DoubleToString(profit, 2));

      LogRow("EXIT", slot, dir, exitPrice, g_exitLevel[slot][dx], 0, lots,
             StringFormat("%s pl=%s", reason, DoubleToString(profit, 2)));
     }

   if(closedSomething)
      ForgetTrade(slot, dx);
   return(true);
  }

void CloseEverything(const string reason)
  {
   for(int slot = 0; slot < SLOT_COUNT; slot++)
      for(int dx = 0; dx < DX_COUNT; dx++)
         if(CountOpenDir(slot, DirOf(dx)) > 0)
            CloseDir(slot, DirOf(dx), reason);
  }

//+------------------------------------------------------------------+
//| Part one of the exit: the slice taken at the target, on TOUCH    |
//|                                                                  |
//| MT4 gives the REMAINDER of a partially closed position a NEW     |
//| ticket. Anything that remembers the old ticket has to be told.   |
//+------------------------------------------------------------------+
void TakePartialAtTarget(const int slot, const int dir)
  {
   int dx = DirIndex(dir);

   if(g_partialDone[slot][dx])                 return;
   if(g_target[slot][dx] <= 0.0)               return;
   if(InpPartialClosePct <= 0.0)               return;   // no target action
   if(g_fullAtTarget[slot][dx])                return;   // a resting TP handles it
   if(!SelectDirOrder(slot, dir))              return;

   int    ticket = OrderTicket();
   double lots   = OrderLots();
   double target = g_target[slot][dx];

   RefreshRates();
   //--- a resting order fills when the tradeable side reaches the level
   bool touched = (dir == DIR_LONG) ? (Bid >= target) : (Ask <= target);
   if(!touched)
      return;

   double partialLots = 0.0;
   if(!PartialIsPossible(lots, partialLots))
     {
      //--- the remainder is already too small to split again; take it all
      PrintFormat("[%s] %s %s target touched but %s lots cannot be split - "
                  "closing the whole position.",
                  InpTradeComment, SlotName(slot), DirName(dir),
                  DoubleToString(lots, 2));
      CloseDir(slot, dir, "target touched (unsplittable)");
      return;
     }

   bool ok = false;
   for(int attempt = 0; attempt <= InpOrderRetries; attempt++)
     {
      RefreshRates();
      double price = (dir == DIR_LONG) ? Bid : Ask;
      ok = OrderClose(ticket, partialLots, NormalizePrice(price),
                      InpSlippagePoints, clrSeaGreen);
      if(ok)
         break;

      int err = GetLastError();
      PrintFormat("[%s] %s %s partial close of %s failed (attempt %d/%d), error %d",
                  InpTradeComment, SlotName(slot), DirName(dir),
                  DoubleToString(partialLots, 2), attempt+1, InpOrderRetries+1, err);
      if(!IsRetryableError(err))
         break;
      Sleep(400);
     }

   if(!ok)
     {
      LogRow("PARTIAL_FAILED", slot, dir, target, g_exitLevel[slot][dx],
             target, partialLots, "partial close rejected");
      return;
     }

   g_partialDone[slot][dx] = true;

   //--- re-resolve: the runner carries a different ticket now
   if(SelectDirOrder(slot, dir))
      g_ticket[slot][dx] = OrderTicket();

   double booked = 0.0;
   if(OrderSelect(ticket, SELECT_BY_TICKET, MODE_HISTORY))
      booked = OrderProfit() + OrderSwap() + OrderCommission();

   //--- optionally protect the runner at entry, on a CLOSE basis to stay
   //--- consistent with how every other stop in this EA works
   if(InpMoveStopAfterPartial && g_entryPrice[slot][dx] > 0.0)
     {
      g_exitLevel[slot][dx] = g_entryPrice[slot][dx];
      PrintFormat("[%s] %s %s runner stop moved to entry %s (close basis)",
                  InpTradeComment, SlotName(slot), DirName(dir),
                  DoubleToString(g_entryPrice[slot][dx], Digits));
     }

   UpdateTradeState(slot, dx);

   PrintFormat("[%s] %s %s TARGET TOUCHED at %s - closed %s of %s lots, "
               "P/L %s. Runner #%d holds to the NY close.",
               InpTradeComment, SlotName(slot), DirName(dir),
               DoubleToString(target, Digits), DoubleToString(partialLots, 2),
               DoubleToString(lots, 2), DoubleToString(booked, 2),
               g_ticket[slot][dx]);

   LogRow("PARTIAL", slot, dir, target, g_exitLevel[slot][dx], target, partialLots,
          StringFormat("target touched pl=%s runner=%s",
                       DoubleToString(booked, 2),
                       DoubleToString(lots - partialLots, 2)));
  }

//+------------------------------------------------------------------+
//| Reconcile a position the BROKER closed                           |
//+------------------------------------------------------------------+
void ReconcileClosed(const int slot, const int dir)
  {
   int dx = DirIndex(dir);
   if(g_ticket[slot][dx] <= 0)
      return;
   if(CountOpenDir(slot, dir) > 0)
      return;

   int ticket = g_ticket[slot][dx];
   if(!OrderSelect(ticket, SELECT_BY_TICKET, MODE_HISTORY))
     {
      ForgetTrade(slot, dx);
      return;
     }
   if(OrderCloseTime() == 0)
      return;

   double exitPrice = OrderClosePrice();
   double profit    = OrderProfit() + OrderSwap() + OrderCommission();
   double tp        = OrderTakeProfit();
   double sl        = OrderStopLoss();
   double tolerance = MathMax(g_pointsToPrice * 5, MinStopDistance());

   string reason = "closed externally";
   if(tp > 0.0 && MathAbs(exitPrice - tp) <= tolerance)
      reason = "target touched";
   else if(sl > 0.0 && MathAbs(exitPrice - sl) <= tolerance)
      reason = "disaster stop";

   PrintFormat("[%s] %s %s #%d closed by the broker (%s) at %s, P/L %s",
               InpTradeComment, SlotName(slot), DirName(dir), ticket, reason,
               DoubleToString(exitPrice, Digits), DoubleToString(profit, 2));

   LogRow("EXIT", slot, dir, exitPrice, g_exitLevel[slot][dx], tp, OrderLots(),
          StringFormat("%s pl=%s", reason, DoubleToString(profit, 2)));

   ForgetTrade(slot, dx);
  }

//+------------------------------------------------------------------+
//| Part two of the exit: the hard stop at the NY close              |
//+------------------------------------------------------------------+
void EnforceHardExit(const datetime nowBroker)
  {
   datetime lastClose = PrevHardExit(nowBroker);

   for(int slot = 0; slot < SLOT_COUNT; slot++)
      for(int dx = 0; dx < DX_COUNT; dx++)
        {
         int dir = DirOf(dx);
         if(!SelectDirOrder(slot, dir))
            continue;
         //--- a position opened before the most recent NY close has outlived
         //--- its session; this also recovers after a terminal restart
         if(OrderOpenTime() < lastClose)
            CloseDir(slot, dir, "NY close");
        }
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
   return(false);
  }

bool SpreadAcceptable()
  {
   if(InpMaxSpreadPoints <= 0)
      return(true);
   return((Ask - Bid) / g_pointsToPrice <= InpMaxSpreadPoints);
  }

//--- vetoes that apply to the whole flavor, whichever way it wants to go
bool GlobalEntryAllowed(const int slot, const datetime nowBroker, string &why)
  {
   if(!SlotEnabled(slot))
     { why = "mode off"; return(false); }
   if(!WeekdayAllowed(nowBroker))
     { why = "weekday off"; return(false); }
   if(g_atr5 <= 0.0)
     { why = "no ATR"; return(false); }
   if(g_tradesToday[slot] >= InpMaxTradesPerDay)
     { why = StringFormat("daily cap %d", InpMaxTradesPerDay); return(false); }
   if(InpMode == MODE_BOTH && InpOneTradeAcrossModes && CountOpenAnySlot() > 0)
     { why = "other flavor in market"; return(false); }
   if(!SpreadAcceptable())
     { why = "spread"; return(false); }
   if(nowBroker + InpNoNewTradesBeforeCloseM*60 >= NextHardExit(nowBroker))
     { why = "near NY close"; return(false); }
   return(true);
  }

//--- vetoes specific to one direction
bool DirectionAllowed(const int slot, const int dir, string &why)
  {
   if(dir == DIR_LONG && !InpTradeLongs)
     { why = "longs off"; return(false); }
   if(dir == DIR_SHORT && !InpTradeShorts)
     { why = "shorts off"; return(false); }

   //--- THE ONE-PER-DIRECTION RULE. A long and a short may be live together,
   //--- but never two longs.
   if(CountOpenDir(slot, dir) >= g_maxOpenPerDir)
     { why = StringFormat("%s already open", DirName(dir)); return(false); }

   if(InpRequireReset && !g_armed[slot][DirIndex(dir)])
     { why = StringFormat("%s not re-armed", DirName(dir)); return(false); }

   return(true);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  SIGNALS - one closed bar of InpEntryTF at a time               |
//|                                                                  |
//+------------------------------------------------------------------+

//--- part one of the exit's sibling: the close-based stop, which governs the
//--- runner just as it governed the full position
void EvaluateCloseStop(const int slot, const double close)
  {
   //--- with a touch stop the broker holds it; there is nothing to evaluate
   if(InpStopStyle == STOP_ON_TOUCH)
      return;

   for(int dx = 0; dx < DX_COUNT; dx++)
     {
      int dir = DirOf(dx);
      if(CountOpenDir(slot, dir) == 0)
         continue;

      RecallTrade(slot, dx);

      //--- A close-based stop lives in EA memory, so losing it means the
      //--- position runs with no structural stop at all - the single worst
      //--- failure this design can have. Rebuild it from the flavor's own
      //--- levels rather than shrug and carry on.
      if(g_exitLevel[slot][dx] <= 0.0)
        {
         double lh, ll, sh, sl;
         if(SlotLevels(slot, lh, ll, sh, sl))
           {
            g_exitLevel[slot][dx] = (dir == DIR_LONG) ? sl : sh;
            UpdateTradeState(slot, dx);
            PrintFormat("[%s] %s %s stop level was missing and has been rebuilt "
                        "from today's levels: %s. Check this trade by hand.",
                        InpTradeComment, SlotName(slot), DirName(dir),
                        DoubleToString(g_exitLevel[slot][dx], Digits));
           }
         else
           {
            Alert(StringFormat("%s %s %s: OPEN POSITION WITH NO STRUCTURAL STOP. "
                               "Only the disaster stop and the NY close will exit "
                               "it. Close it by hand if that is not acceptable.",
                               InpTradeComment, Symbol(), DirName(dir)));
            continue;
           }
        }

      bool stopped = (dir == DIR_LONG) ? (close < g_exitLevel[slot][dx])
                                       : (close > g_exitLevel[slot][dx]);
      if(stopped)
        {
         PrintFormat("[%s] %s %s close-based stop: bar closed at %s, level %s%s",
                     InpTradeComment, SlotName(slot), DirName(dir),
                     DoubleToString(close, Digits),
                     DoubleToString(g_exitLevel[slot][dx], Digits),
                     (g_partialDone[slot][dx] ? " (runner)" : ""));
         CloseDir(slot, dir, "close-based stop");
        }
     }
  }

//--- re-arming, only when InpRequireReset is on: a direction that has traded
//--- cannot trade again until price closes back INSIDE the range
void EvaluateReArm(const int slot, const double close,
                   const double levelHigh, const double levelLow)
  {
   if(!InpRequireReset)
      return;

   for(int dx = 0; dx < DX_COUNT; dx++)
     {
      int dir = DirOf(dx);
      if(g_armed[slot][dx])
         continue;
      if(CountOpenDir(slot, dir) > 0)
         continue;

      bool backInside = (dir == DIR_LONG) ? (close <= levelHigh)
                                          : (close >= levelLow);
      if(backInside)
        {
         g_armed[slot][dx] = true;
         PrintFormat("[%s] %s %s re-armed - price closed back inside the range",
                     InpTradeComment, SlotName(slot), DirName(dir));
        }
     }
  }

void EvaluateEntry(const int slot, const datetime nowBroker,
                   const datetime barClose, const double close)
  {
   string why = "";
   if(!GlobalEntryAllowed(slot, nowBroker, why))
     { g_skipReason[slot] = why; return; }

   double levelHigh, levelLow, stopHigh, stopLow;
   if(!SlotLevels(slot, levelHigh, levelLow, stopHigh, stopLow))
     { g_skipReason[slot] = "levels not ready"; return; }

   datetime levelReadyAt = (slot == SLOT_ASIA)
                           ? g_asiaEndB
                           : g_trigOpenB + PeriodSeconds(InpTriggerTF);
   if(barClose <= levelReadyAt)
     { g_skipReason[slot] = "bar predates level"; return; }

   //--- a level formed before the most recent hard exit belongs to a session
   //--- that is already over, and must never open a trade
   if(levelReadyAt <= PrevHardExit(nowBroker))
     { g_skipReason[slot] = "level expired at NY close"; return; }

   double rangePoints = (levelHigh - levelLow) / g_pointsToPrice;
   if(InpMinRangePoints > 0 && rangePoints < InpMinRangePoints)
     { g_skipReason[slot] = "range too narrow"; return; }
   if(InpMaxRangePoints > 0 && rangePoints > InpMaxRangePoints)
     { g_skipReason[slot] = "range too wide"; return; }

   double buffer = InpBreakoutBufferPoints * g_pointsToPrice;
   double target = InpTPPctOfATR / 100.0 * g_atr5;

   int    dir        = DIR_NONE;
   double structural = 0.0;
   double tp         = 0.0;

   if(close > levelHigh + buffer)
     {
      dir = DIR_LONG;   structural = stopLow;   tp = stopLow + target;
     }
   else if(close < levelLow - buffer)
     {
      dir = DIR_SHORT;  structural = stopHigh;  tp = stopHigh - target;
     }
   else
     { g_skipReason[slot] = "no breakout"; return; }

   if(!DirectionAllowed(slot, dir, why))
     { g_skipReason[slot] = why; return; }

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

   //--- the range is wider than the ATR-derived target, so the target sits at
   //--- or behind the entry. Skip the setup rather than fudge the target.
   bool targetBehind = (dir == DIR_LONG) ? (tp <= entry) : (tp >= entry);
   if(targetBehind)
     {
      g_skipReason[slot] = "target behind entry";
      PrintFormat("[%s] %s skipped: range %.0f pts exceeds %.0f%% of ATR5 "
                  "(%.0f pts), target %s is behind entry %s",
                  InpTradeComment, SlotName(slot), rangePoints, InpTPPctOfATR,
                  target / g_pointsToPrice, DoubleToString(tp, Digits),
                  DoubleToString(entry, Digits));
      LogRow("SKIP", slot, dir, entry, structural, tp, 0, "target behind entry");
      return;
     }

   OpenTrade(slot, dir, structural, tp);
  }

//--- everything that happens once per closed signal bar, in the order it has
//--- to happen: exits, then re-arming, then entries
void ProcessBar(const int slot, const datetime nowBroker)
  {
   double close = iClose(NULL, InpEntryTF, 1);
   datetime barClose = iTime(NULL, InpEntryTF, 1) + PeriodSeconds(InpEntryTF);

   EvaluateCloseStop(slot, close);

   double levelHigh, levelLow, stopHigh, stopLow;
   if(SlotLevels(slot, levelHigh, levelLow, stopHigh, stopLow))
      EvaluateReArm(slot, close, levelHigh, levelLow);

   EvaluateEntry(slot, nowBroker, barClose, close);
  }

//+------------------------------------------------------------------+
//|                                                                  |
//|  DISPLAY                                                         |
//|                                                                  |
//+------------------------------------------------------------------+
#define OBJ_PREFIX "ABEA2_"

void DrawBox(const string name, const datetime t1, const double p1,
             const datetime t2, const double p2, const color clr)
  {
   string id = OBJ_PREFIX + name;
   if(ObjectFind(0, id) < 0)
     {
      ObjectCreate(0, id, OBJ_RECTANGLE, 0, t1, p1, t2, p2);
      ObjectSetInteger(0, id, OBJPROP_COLOR, clr);
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
      ObjectCreate(0, id, OBJ_TREND, 0, t1, price,
                   TimeCurrent() + PeriodSeconds()*20, price);
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

void DropLine(const string name)
  {
   ObjectDelete(0, OBJ_PREFIX + name);
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
      for(int dx = 0; dx < DX_COUNT; dx++)
        {
         int dir = DirOf(dx);
         string tag = StringFormat("%s_%s", SlotName(slot), DirName(dir));
         if(SelectDirOrder(slot, dir))
           {
            if(g_target[slot][dx] > 0.0)
               DrawLine("tp_" + tag, OrderOpenTime(), g_target[slot][dx],
                        InpColorTP, STYLE_SOLID,
                        tag + (g_partialDone[slot][dx] ? " target taken" : " target (touch)"));
            if(g_exitLevel[slot][dx] > 0.0)
               DrawLine("sl_" + tag, OrderOpenTime(), g_exitLevel[slot][dx],
                        InpColorSL, STYLE_SOLID, tag + " stop (close)");
           }
         else
           {
            DropLine("tp_" + tag);
            DropLine("sl_" + tag);
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

   string exitPlan = (InpPartialClosePct <= 0.0)
                     ? "no target, all to NY close"
                     : (InpPartialClosePct >= 100.0
                        ? "100% at target"
                        : StringFormat("%.0f%% at target, %.0f%% to NY close",
                                       InpPartialClosePct, 100.0 - InpPartialClosePct));

   string text = StringFormat("%s v2  %s  [%s]\n", InpTradeComment, Symbol(), modeText);
   text += StringFormat("TF  %s breaks the range%s\n",
                        StringSubstr(EnumToString(InpEntryTF), 7),
                        (InpMode == MODE_ASIA_RANGE ? "" :
                         StringFormat("  |  trigger candle %s",
                                      StringSubstr(EnumToString(InpTriggerTF), 7))));
   text += StringFormat("Server %s   UTC %s   offset %+.1fh\n",
                        TimeToString(nowBroker, TIME_MINUTES),
                        TimeToString(BrokerToUtc(nowBroker), TIME_MINUTES),
                        BrokerOffsetAtUtc(BrokerToUtc(nowBroker)) / 3600.0);
   text += StringFormat("ATR%d = %.0f pts | target %.0f%% = %.0f pts | exit: %s\n",
                        InpATRDays, g_atr5 / g_pointsToPrice, InpTPPctOfATR,
                        g_atr5 * InpTPPctOfATR / 100.0 / g_pointsToPrice, exitPlan);

   if(g_asiaReady)
      text += StringFormat("Asia  %s - %s   H %s  L %s  (%.0f pts)\n",
                           TimeToString(g_asiaStartB, TIME_MINUTES),
                           TimeToString(g_asiaEndB, TIME_MINUTES),
                           DoubleToString(g_asiaHigh, Digits),
                           DoubleToString(g_asiaLow, Digits),
                           (g_asiaHigh - g_asiaLow) / g_pointsToPrice);
   else
      text += "Asia  building...\n";

   if(SlotEnabled(SLOT_TRIGGER))
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

      text += StringFormat("%-6s entries %d/%d", SlotName(slot),
                           g_tradesToday[slot], InpMaxTradesPerDay);

      int live = 0;
      for(int dx = 0; dx < DX_COUNT; dx++)
        {
         int dir = DirOf(dx);
         if(!SelectDirOrder(slot, dir))
            continue;
         live++;
         text += StringFormat("\n        %s %s lots  %s %s  target %s%s",
                              DirName(dir), DoubleToString(OrderLots(), 2),
                              (InpStopStyle == STOP_ON_TOUCH ? "stop(touch)" : "stop(close)"),
                              DoubleToString(g_exitLevel[slot][dx], Digits),
                              DoubleToString(g_target[slot][dx], Digits),
                              (g_partialDone[slot][dx] ? "  [partial taken]" : ""));
         if(InpStopStyle == STOP_ON_CLOSE && OrderStopLoss() > 0.0)
            text += StringFormat("\n               broker S/L %s = disaster stop, not the level",
                                 DoubleToString(OrderStopLoss(), Digits));
        }

      if(live == 0 && StringLen(g_skipReason[slot]) > 0)
         text += "   idle: " + g_skipReason[slot];
      text += "\n";
     }

   Comment(text);
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
  }

//+------------------------------------------------------------------+
//| Day rollover                                                     |
//+------------------------------------------------------------------+
void RollDay(const datetime nowBroker)
  {
   datetime today = (datetime)((long)nowBroker - ((long)nowBroker % 86400));
   if(today == g_dayKey)
      return;

   g_dayKey = today;
   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      g_tradesToday[slot] = 0;
      g_skipReason[slot]  = "";
      for(int dx = 0; dx < DX_COUNT; dx++)
         g_armed[slot][dx] = true;
     }

   g_atr5 = ComputeATR();
   PrintFormat("[%s] New trading day %s   ATR%d = %s (%.0f pts)",
               InpTradeComment, TimeToString(today, TIME_DATE), InpATRDays,
               DoubleToString(g_atr5, Digits), g_atr5 / g_pointsToPrice);
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
   if(InpMaxOpenPerDirection < 1)
     { Print("InpMaxOpenPerDirection must be at least 1."); ok = false; }
   if(InpMaxOpenPerDirection > 1)
      Print("NOTE: this build tracks ONE position per direction - one ticket, "
            "one stop level, one target, one partial-fill state. "
            "InpMaxOpenPerDirection is treated as 1. Use InpMaxTradesPerDay to "
            "allow more entries per day; they queue rather than stack.");
   if(InpMagicAsia == InpMagicTrigger)
     { Print("The two magic numbers must differ."); ok = false; }
   if(!InpTradeLongs && !InpTradeShorts)
     { Print("Both directions are disabled - the EA would never trade."); ok = false; }
   if(InpPartialClosePct < 0.0 || InpPartialClosePct > 100.0)
     { Print("InpPartialClosePct must be between 0 and 100."); ok = false; }

   int trigBarMinutes = PeriodSeconds(InpTriggerTF) / 60;
   if(trigBarMinutes > 0 && trigBarMinutes < 1440)
     {
      int minuteOfDay = InpTriggerHour*60 + InpTriggerMin;
      if(minuteOfDay % trigBarMinutes != 0)
         PrintFormat("WARNING: %02d:%02d does not fall on a %d-minute bar boundary. "
                     "No trigger candle will be found.",
                     InpTriggerHour, InpTriggerMin, trigBarMinutes);
     }

   //--- a scaled exit needs a position big enough to slice
   if(InpPartialClosePct > 0.0 && InpPartialClosePct < 100.0 && InpLotMode == LOT_FIXED)
     {
      double dummy = 0.0;
      if(!PartialIsPossible(InpFixedLots, dummy))
         PrintFormat("WARNING: %s lots cannot be split %.0f/%.0f above the %s "
                     "minimum. The target will close the WHOLE position instead "
                     "of scaling out.",
                     DoubleToString(InpFixedLots, 2), InpPartialClosePct,
                     100.0 - InpPartialClosePct,
                     DoubleToString(MarketInfo(Symbol(), MODE_MINLOT), 2));
     }

   if(InpStopStyle == STOP_ON_CLOSE)
      Print("NOTE: the structural stop is CLOSE-BASED, so it is held by the EA, "
            "not by the broker. Price may trade through the level intrabar and "
            "the trade survives, provided the bar closes back on the right side. "
            "The S/L shown on the order in the terminal is the DISASTER stop, "
            "further out - it is not the structural stop. Set InpStopStyle = "
            "STOP_ON_TOUCH if you want the broker stop to sit on the level and "
            "fill the moment price reaches it.");
   else
      Print("NOTE: the structural stop is ON TOUCH. The broker stop sits on the "
            "level and fills the moment price trades there. The close-based rule "
            "is disabled, and the disaster-stop settings are not used.");

   if(InpStopStyle == STOP_ON_CLOSE && InpProtectiveSLMode == PSL_ATR_PCT)
      Print("TIP: in trigger-candle mode the structural stop is one candle deep, "
            "so an ATR-sized disaster pad can sit far below it and turn a small "
            "planned loss into a large real one. InpProtectiveSLMode = "
            "PSL_STRUCT_PCT keeps the pad proportional to the trade's own risk.");

   if(InpProtectiveSLMode == PSL_NONE && InpStopStyle == STOP_ON_CLOSE)
      Print("WARNING: no broker stop will be attached. If this terminal or the "
            "VPS goes down with a position open, nothing limits the loss.");

   if(InpPartialClosePct > 0.0 && InpPartialClosePct < 100.0)
      Print("NOTE: with a scaled exit the target is watched by the EA rather "
            "than resting at the broker, because a broker take-profit closes a "
            "whole position. If the terminal is offline when price reaches the "
            "target, the slice is not taken. The disaster stop stays broker-side.");

   return(ok);
  }

void ResolveBrokerClock()
  {
   if(InpBrokerOffsetMode == BOFF_MANUAL || IsTesting())
     {
      g_brokerWinterOffsetSec = InpBrokerWinterOffsetHours * 3600;
      if(IsTesting() && InpBrokerOffsetMode == BOFF_AUTO)
         Print("Strategy Tester: TimeGMT() is not meaningful here, so the manual "
               "winter offset is used. Check InpBrokerWinterOffsetHours.");
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
               InpTradeComment, g_brokerWinterOffsetSec / 3600.0,
               (InpBrokerDSTRule == DST_US ? "US" : (InpBrokerDSTRule == DST_EU ? "EU" : "none")),
               BrokerOffsetAtUtc(BrokerToUtc(TimeCurrent())) / 3600.0);
  }

int OnInit()
  {
   if(!ValidateInputs())
      return(INIT_PARAMETERS_INCORRECT);

   g_pointsToPrice   = Point;
   g_maxOpenPerDir   = 1;
   g_stopLevelPoints = (int)MarketInfo(Symbol(), MODE_STOPLEVEL);
   PrintFormat("[%s] %s: digits=%d point=%s broker stop level=%d points",
               InpTradeComment, Symbol(), Digits,
               DoubleToString(g_pointsToPrice, 8), g_stopLevelPoints);

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      g_tradesToday[slot]   = 0;
      g_lastSignalBar[slot] = iTime(NULL, InpEntryTF, 0);
      g_skipReason[slot]    = "";
      for(int dx = 0; dx < DX_COUNT; dx++)
        {
         g_ticket[slot][dx]       = 0;
         g_exitLevel[slot][dx]    = 0.0;
         g_target[slot][dx]       = 0.0;
         g_entryPrice[slot][dx]   = 0.0;
         g_partialDone[slot][dx]  = false;
         g_fullAtTarget[slot][dx] = false;
         g_armed[slot][dx]        = true;
         RecallTrade(slot, dx);        // survive a restart holding a position
        }
     }

   ResolveBrokerClock();

   g_dayKey = 0;
   RollDay(TimeCurrent());

   datetime nowBroker = TimeCurrent();
   UpdateAsiaRange(nowBroker);
   if(SlotEnabled(SLOT_TRIGGER))
      UpdateTriggerCandle(nowBroker);

   //--- MT4's Strategy Tester only serves the timeframe being tested and
   //--- higher. Asking it for a LOWER one returns nothing, the new-bar check
   //--- never fires, and the EA sits there taking no trades and saying
   //--- nothing about why. That is worth shouting about.
   if(IsTesting() && PeriodSeconds(InpEntryTF) < PeriodSeconds((ENUM_TIMEFRAMES)Period()))
      Alert(StringFormat("%s: the Strategy Tester is running on %s but InpEntryTF "
                         "is %s. MT4 cannot serve a timeframe LOWER than the one "
                         "being tested, so NO TRADES will be taken. Set the "
                         "tester's Period to %s and use Every tick.",
                         InpTradeComment,
                         StringSubstr(EnumToString((ENUM_TIMEFRAMES)Period()), 7),
                         StringSubstr(EnumToString(InpEntryTF), 7),
                         StringSubstr(EnumToString(InpEntryTF), 7)));

   int signalBars = iBars(NULL, InpEntryTF);
   if(signalBars <= 2 || iTime(NULL, InpEntryTF, 1) == 0)
      Alert(StringFormat("%s: no usable %s history on %s (%d bars). The EA cannot "
                         "see a signal bar close, so it will take no trades. Open "
                         "an %s chart for this symbol once to pull the history.",
                         InpTradeComment, StringSubstr(EnumToString(InpEntryTF), 7),
                         Symbol(), signalBars,
                         StringSubstr(EnumToString(InpEntryTF), 7)));
   else
      PrintFormat("[%s] signal timeframe %s has %d bars, most recent close %s.",
                  InpTradeComment, StringSubstr(EnumToString(InpEntryTF), 7),
                  signalBars, TimeToString(iTime(NULL, InpEntryTF, 1) +
                                           PeriodSeconds(InpEntryTF), TIME_DATE|TIME_MINUTES));

   PrintFormat("[%s] v2 ready on %s. The %s candle both measures the range and "
               "must CLOSE beyond it to enter; the trigger candle is %s. "
               "Up to %d entries/day, %d open per direction. Hard exit %s.",
               InpTradeComment, Symbol(),
               StringSubstr(EnumToString(InpEntryTF), 7),
               StringSubstr(EnumToString(InpTriggerTF), 7),
               InpMaxTradesPerDay, g_maxOpenPerDir,
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

   //--- the Asia range is always maintained: the candle flavor can be
   //--- configured to anchor against it
   UpdateAsiaRange(nowBroker);
   if(SlotEnabled(SLOT_TRIGGER))
      UpdateTriggerCandle(nowBroker);

   //--- pick up anything the broker closed behind our back
   for(int slot = 0; slot < SLOT_COUNT; slot++)
      for(int dx = 0; dx < DX_COUNT; dx++)
         ReconcileClosed(slot, DirOf(dx));

   if(IsTradeAllowed())
     {
      //--- the hard exit outranks everything
      EnforceHardExit(nowBroker);

      //--- part one of the exit is a TOUCH, so it is checked every tick
      for(int slot = 0; slot < SLOT_COUNT; slot++)
         for(int dx = 0; dx < DX_COUNT; dx++)
            TakePartialAtTarget(slot, DirOf(dx));
     }

   //--- everything close-based happens once per closed signal bar
   datetime currentBar = iTime(NULL, InpEntryTF, 0);

   //--- a zero here means the signal timeframe has no data. Without this the
   //--- new-bar check would simply never fire and the EA would look idle.
   if(currentBar == 0)
     {
      static datetime lastBlindWarning = 0;
      if(nowBroker - lastBlindWarning > 300)
        {
         lastBlindWarning = nowBroker;
         PrintFormat("[%s] no %s data available - no signal bars to read, so no "
                     "trades can be taken. Open an %s chart for %s once.",
                     InpTradeComment, StringSubstr(EnumToString(InpEntryTF), 7),
                     StringSubstr(EnumToString(InpEntryTF), 7), Symbol());
         g_skipReason[SLOT_ASIA]    = "no signal TF data";
         g_skipReason[SLOT_TRIGGER] = "no signal TF data";
        }
     }

   for(int slot = 0; slot < SLOT_COUNT; slot++)
     {
      if(!SlotEnabled(slot))
         continue;
      if(currentBar == 0)
         continue;
      if(currentBar == g_lastSignalBar[slot])
         continue;
      if(!IsTradeAllowed())
         continue;

      g_lastSignalBar[slot] = currentBar;
      ProcessBar(slot, nowBroker);
     }

   RedrawObjects();
   UpdatePanel(nowBroker);
  }
//+------------------------------------------------------------------+
