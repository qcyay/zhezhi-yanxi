"""Frozen entry point; never invokes pip or an external Python interpreter."""
import sys
import app

if __name__ == '__main__':
    if '--self-test' in sys.argv:
        from package_check import check
        check()
    else:
        app.main()
