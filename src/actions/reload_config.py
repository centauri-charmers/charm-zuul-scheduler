#!/usr/bin/env python3

import subprocess

if __name__ == '__main__':
    subprocess.check_call(['zuul-scheduler', 'full-reconfigure'])
