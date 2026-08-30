"""WSGI entry point for a real hosted ScoreMax V6.4.0 pilot.

The hosting environment must supply production secrets, database path and SMTP settings.
This module deliberately does not weaken app.py's production safety gates.
"""
import os
if os.environ.get('SCOREMAX_ENV','').strip().lower()!='production':
    raise RuntimeError('Set SCOREMAX_ENV=production for the hosted ScoreMax entry point.')
import app as scoremax
scoremax.init()
application=scoremax.app
app=application
