import os
from flask import Blueprint, render_template, send_from_directory, current_app, session, redirect, url_for

views = Blueprint('views', __name__)

@views.route('/')
def home():
    return render_template("general/home.html")

@views.route('/app')
def pwa_app_launcher():
    """
    Dedicated authentication-aware app entry launcher.
    Manifest start_url points here.
    If authenticated -> redirect('/admin')
    If unauthenticated -> redirect('/login')
    """
    if session.get('logged_in'):
        resp = redirect(url_for('auth.admin'))
    else:
        resp = redirect(url_for('auth.login'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    return resp

@views.route('/service-worker.js')
@views.route('/sw.js')
def service_worker():
    static_dir = os.path.join(current_app.root_path, 'static')
    response = send_from_directory(static_dir, 'sw.js', mimetype='application/javascript')
    response.headers['Service-Worker-Allowed'] = '/'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    return response

@views.route('/manifest.json')
def manifest():
    static_dir = os.path.join(current_app.root_path, 'static')
    response = send_from_directory(static_dir, 'manifest.json', mimetype='application/manifest+json')
    response.headers['Cache-Control'] = 'public, max-age=3600'
    return response

@views.route('/offline.html')
def offline():
    static_dir = os.path.join(current_app.root_path, 'static')
    return send_from_directory(static_dir, 'offline.html')

@views.route('/download/app')
@views.route('/download/apk')
@views.route('/download/ImageTraditional.apk')
def download_apk():
    """
    Serves the private compiled Image Traditional Android APK to authenticated admins.
    Security: Strictly protected by session authentication.
    """
    if not session.get('logged_in'):
        return redirect(url_for('auth.login'))

    downloads_dir = os.path.join(current_app.root_path, 'static', 'downloads')
    apk_file = os.path.join(downloads_dir, 'ImageTraditional.apk')

    if not os.path.exists(apk_file):
        import shutil
        # Check standard build artifact locations
        build_release = os.path.join(current_app.root_path, '..', 'android', 'app', 'build', 'outputs', 'apk', 'release', 'ImageTraditional.apk')
        build_debug = os.path.join(current_app.root_path, '..', 'android', 'app', 'build', 'outputs', 'apk', 'debug', 'ImageTraditional-debug.apk')
        
        source_apk = None
        if os.path.exists(build_release):
            source_apk = build_release
        elif os.path.exists(build_debug):
            source_apk = build_debug

        if source_apk:
            os.makedirs(downloads_dir, exist_ok=True)
            shutil.copy2(source_apk, apk_file)

    if os.path.exists(apk_file):
        return send_from_directory(
            downloads_dir,
            'ImageTraditional.apk',
            as_attachment=True,
            mimetype='application/vnd.android.package-archive',
            download_name='ImageTraditional.apk'
        )
    return redirect(url_for('auth.admin'))