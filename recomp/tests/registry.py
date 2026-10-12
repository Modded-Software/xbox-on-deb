"""Test registry and runner for the recomp test suite.

Tests are plain functions decorated with @test("..."); run_all() runs every
registered test against one Game and prints a PASS/FAIL summary.
"""
import signal

_REGISTRY = []


def test(name=None, timeout=None):
    def decorate(fn):
        _REGISTRY.append((name or fn.__name__, fn, timeout))
        return fn
    return decorate


def registered():
    return list(_REGISTRY)


def _test_alarm(_signum, _frame):
    raise TimeoutError("test exceeded its time limit (game may have hung)")


def run_all(game, only=None, per_test_timeout=90):
    passed, failed = 0, 0
    previous = signal.signal(signal.SIGALRM, _test_alarm)
    for name, fn, timeout in registered():
        if only and only not in name:
            continue
        signal.alarm(timeout or per_test_timeout)
        try:
            game.focus()
            fn(game)
            print(f"  PASS  {name}")
            passed += 1
        except Exception as error:
            print(f"  FAIL  {name}: {type(error).__name__}: {error}")
            failed += 1
        finally:
            signal.alarm(0)
    signal.signal(signal.SIGALRM, previous)
    print(f"\n{passed} passed, {failed} failed")
    return failed == 0