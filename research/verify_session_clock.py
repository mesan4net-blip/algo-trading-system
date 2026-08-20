#!/usr/bin/env python3
"""
verify_session_clock.py

A line-for-line Python port of the time functions inside
phase3/ea/AsiaBreakout_EA_v1.mq4, so the daylight-saving math can be checked
without a running MT4 terminal.

MQL4 has no timezone database. The EA therefore carries its own DST rules, and
a wrong rule silently shifts every session by an hour - the kind of bug that
does not raise an error, it just quietly trades the wrong window for three
weeks a year. This script is the proof that the rules are right.

Run:  python3 research/verify_session_clock.py
"""
import calendar
from datetime import datetime, timedelta

def stamp(y,mo,d,h=0,mi=0): return calendar.timegm((y,mo,d,h,mi,0,0,0,0))
def show(t): return datetime.utcfromtimestamp(t).strftime('%Y-%m-%d %H:%M %a')
def dow(t): return (datetime.utcfromtimestamp(t).weekday()+1)%7   # 0=Sunday, as in MQL
def days_in_month(y,m): return calendar.monthrange(y,m)[1]

def nth_sunday(y,mo,nth):
    first = stamp(y,mo,1)
    return first + ((7-dow(first))%7 + 7*(nth-1))*86400

def last_sunday(y,mo):
    last = stamp(y,mo,days_in_month(y,mo))
    return last - dow(last)*86400

def year_of(t): return datetime.utcfromtimestamp(t).year

def is_eu_dst(utc):
    y = year_of(utc)
    return last_sunday(y,3)+3600 <= utc < last_sunday(y,10)+3600

def is_us_dst(utc):
    y = year_of(utc)
    return nth_sunday(y,3,2)+7*3600 <= utc < nth_sunday(y,11,1)+6*3600

WINTER = 2*3600          # InpBrokerWinterOffsetHours = 2
BROKER_RULE = 'US'       # InpBrokerDSTRule = DST_US

def dst_active(rule, utc):
    return is_us_dst(utc) if rule=='US' else (is_eu_dst(utc) if rule=='EU' else False)

def broker_off(utc):  return WINTER + (3600 if dst_active(BROKER_RULE, utc) else 0)
def utc_to_broker(u): return u + broker_off(u)
def broker_to_utc(b):
    g = b - WINTER
    u = b - broker_off(g)
    return b - broker_off(u)

def tz_off(tz, utc):
    if tz=='UTC':     return 0
    if tz=='LONDON':  return 3600 if is_eu_dst(utc) else 0
    if tz=='NEWYORK': return -4*3600 if is_us_dst(utc) else -5*3600
    if tz=='TOKYO':   return 9*3600
    if tz=='BROKER':  return broker_off(utc)

def utc_to_local(tz,u): return u + tz_off(tz,u)
def local_to_utc(tz,l): return l - tz_off(tz, l - tz_off(tz,l))
def local_to_broker(tz,l): return utc_to_broker(local_to_utc(tz,l))

def resolve_completed_session(now_b, tz, sh,sm,eh,em):
    start_min, end_min = sh*60+sm, eh*60+em
    length = (end_min-start_min) if end_min>start_min else (end_min+1440-start_min)
    now_l = utc_to_local(tz, broker_to_utc(now_b))
    d = datetime.utcfromtimestamp(now_l)
    end_l = stamp(d.year,d.month,d.day,eh,em)
    for _ in range(8):
        if end_l <= now_l: break
        end_l -= 86400
    return local_to_broker(tz, end_l-length*60), local_to_broker(tz, end_l)

def resolve_past_local(now_b, tz, h, mi, min_past):
    now_l = utc_to_local(tz, broker_to_utc(now_b))
    d = datetime.utcfromtimestamp(now_l)
    c = stamp(d.year,d.month,d.day,h,mi)
    for _ in range(8):
        if c + min_past <= now_l: break
        c -= 86400
    return local_to_broker(tz, c)

def next_hard_exit(now_b, tz='NEWYORK', h=17, mi=0):
    now_l = utc_to_local(tz, broker_to_utc(now_b))
    d = datetime.utcfromtimestamp(now_l)
    day = stamp(d.year,d.month,d.day)
    for _ in range(8):
        c = day + (h*60+mi)*60
        if c > now_l: return local_to_broker(tz,c)
        day += 86400

def prev_hard_exit(now_b, tz='NEWYORK', h=17, mi=0):
    now_l = utc_to_local(tz, broker_to_utc(now_b))
    d = datetime.utcfromtimestamp(now_l)
    day = stamp(d.year,d.month,d.day)
    for _ in range(8):
        c = day + (h*60+mi)*60
        if c <= now_l: return local_to_broker(tz,c)
        day -= 86400


# ---------------------------------------------------------------------------
# Expectations, for the sessions as shipped:
#
#   Asia (Sydney + Tokyo)  22:00 - 09:00 GMT, fixed (crosses midnight)
#   London first hour      08:00 London local
#   New York close         17:00 New York local
#
# Broker clock: UTC+2 winter, US DST rules (FOREX.com and most MT4 servers).
# ---------------------------------------------------------------------------
ASIA = ("UTC", 22, 0, 9, 0)

EXPECTED = [
    # label,                server "now",          asia start, asia end, trigger, next NY close
    ("summer",              (2026,  7, 15, 14, 0), "01:00", "12:00", "10:00", "2026-07-16 00:00"),
    ("winter",              (2026,  1, 15, 14, 0), "00:00", "11:00", "10:00", "2026-01-16 00:00"),
    ("US on, EU still off", (2026,  3, 15, 14, 0), "01:00", "12:00", "11:00", "2026-03-16 00:00"),
    ("EU off, US still on", (2026, 10, 28, 14, 0), "01:00", "12:00", "11:00", "2026-10-29 00:00"),
]


def hhmm(t):
    return datetime.utcfromtimestamp(t).strftime("%H:%M")


def full(t):
    return datetime.utcfromtimestamp(t).strftime("%Y-%m-%d %H:%M")


def main():
    failures = 0

    print("Asia 22:00-09:00 GMT fixed | London trigger 08:00 local | "
          "NY close 17:00 local\nBroker clock: UTC+2 winter, US DST rules.\n")
    for label, when, exp_start, exp_end, exp_trig, exp_close in EXPECTED:
        now_b = stamp(*when)
        start, end = resolve_completed_session(now_b, *ASIA)
        trig = resolve_past_local(now_b, "LONDON", 8, 0, 3600)
        close = next_hard_exit(now_b)

        got = (hhmm(start), hhmm(end), hhmm(trig), full(close))
        exp = (exp_start, exp_end, exp_trig, exp_close)
        ok = got == exp
        if not ok:
            failures += 1

        print("%-22s server %s  offset UTC%+.0f" %
              (label, full(now_b), broker_off(broker_to_utc(now_b)) / 3600.0))
        print("%-22s Asia %s-%s server | trigger %s server | NY close %s   %s" %
              ("", got[0], got[1], got[2], got[3],
               "ok" if ok else "FAIL expected " + str(exp)))

    # The expired-level guard: a range formed before the most recent NY close
    # must never be tradeable, however the daily counters have been reset.
    print("\nExpired-level guard:")
    guard = [
        ((2026, 1, 15, 22,  0), False),   # mid session, 15:00 New York
        ((2026, 1, 16,  0, 30), True),    # 30 min past the NY close
        ((2026, 1, 16, 11,  0), False),   # next day's Asia session has just ended
    ]
    for when, expect_blocked in guard:
        now_b = stamp(*when)
        _, asia_end = resolve_completed_session(now_b, *ASIA)
        blocked = asia_end <= prev_hard_exit(now_b)
        ok = blocked == expect_blocked
        if not ok:
            failures += 1
        print("  server %s  level from %s  %-10s %s" %
              (full(now_b), full(asia_end),
               "blocked" if blocked else "tradeable", "ok" if ok else "FAIL"))

    # DST boundary instants, checked directly against the published rules.
    print("\nDST boundaries:")
    checks = [
        ("EU 2026 starts",  is_eu_dst(stamp(2026,  3, 29, 1,  0)), True),
        ("EU 2026 before",  is_eu_dst(stamp(2026,  3, 29, 0, 59)), False),
        ("EU 2026 ends",    is_eu_dst(stamp(2026, 10, 25, 1,  0)), False),
        ("US 2026 starts",  is_us_dst(stamp(2026,  3,  8, 7,  0)), True),
        ("US 2026 before",  is_us_dst(stamp(2026,  3,  8, 6, 59)), False),
        ("US 2026 ends",    is_us_dst(stamp(2026, 11,  1, 6,  0)), False),
    ]
    for label, got, exp in checks:
        ok = got == exp
        if not ok:
            failures += 1
        print("  %-16s %-5s %s" % (label, str(got), "ok" if ok else "FAIL expected " + str(exp)))

    print("\n" + ("ALL CHECKS PASSED" if failures == 0 else "%d CHECK(S) FAILED" % failures))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
