from flask import Flask, request, render_template_string
import os, sys, subprocess, warnings

app = Flask(__name__)

FLAG_WEB = os.environ.get('FLAG_WEB', 'flag{web}')
INTERNAL_HOST = os.environ.get('INTERNAL_HOST', 'internal-ctf')
INTERNAL_USER = os.environ.get('INTERNAL_USER', 'ctfuser')
INTERNAL_PASS = os.environ.get('INTERNAL_PASS', 'secret')

app.config['INTERNAL_CREDS'] = {
    'host': INTERNAL_HOST,
    'user': INTERNAL_USER,
    'pass': INTERNAL_PASS
}

@app.route('/')
def index():
    name = request.args.get('name', 'guest')
    template = f'''
    <h1>Hello, {name}!</h1>
    <p>Try to find the flags...</p>
    '''
    return render_template_string(template, warnings=warnings, os=os)

@app.route('/hint')
def hint():
    return "Check the config..."

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)