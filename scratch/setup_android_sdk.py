import os
import sys
import urllib.request
import zipfile
import subprocess
import shutil

TOOLS_DIR = r"F:\android-build-tools"
SDK_DIR = r"F:\android-sdk"
JDK_DIR = os.path.join(TOOLS_DIR, "jdk-17")
GRADLE_DIR = os.path.join(TOOLS_DIR, "gradle-8.7")

os.makedirs(TOOLS_DIR, exist_ok=True)
os.makedirs(SDK_DIR, exist_ok=True)

def download_file(url, target_path, label):
    if os.path.exists(target_path):
        print(f"[{label}] Already exists at {target_path}")
        return
    print(f"[{label}] Downloading from {url}...")
    headers = {'User-Agent': 'Mozilla/5.0'}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp, open(target_path, 'wb') as out:
        total = int(resp.headers.get('content-length', 0))
        downloaded = 0
        block_size = 1024 * 1024
        while True:
            chunk = resp.read(block_size)
            if not chunk:
                break
            out.write(chunk)
            downloaded += len(chunk)
            if total > 0:
                percent = (downloaded / total) * 100
                print(f"\r[{label}] Progress: {percent:.1f}% ({downloaded//(1024*1024)}MB / {total//(1024*1024)}MB)", end='', flush=True)
            else:
                print(f"\r[{label}] Downloaded {downloaded//(1024*1024)}MB", end='', flush=True)
    print()
    print(f"[{label}] Download complete.")

def extract_zip(zip_path, extract_to, label):
    print(f"[{label}] Extracting to {extract_to}...")
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(extract_to)
    print(f"[{label}] Extraction complete.")

def setup_jdk():
    java_exe = os.path.join(JDK_DIR, "bin", "java.exe")
    if os.path.exists(java_exe):
        print(f"[JDK] JDK 17 already setup at {JDK_DIR}")
        return JDK_DIR
    
    jdk_zip = os.path.join(TOOLS_DIR, "temurin-17.zip")
    url = "https://api.adoptium.net/v3/binary/latest/17/ga/windows/x64/jdk/hotspot/normal/eclipse"
    download_file(url, jdk_zip, "JDK 17")
    
    temp_extract = os.path.join(TOOLS_DIR, "jdk_temp")
    os.makedirs(temp_extract, exist_ok=True)
    extract_zip(jdk_zip, temp_extract, "JDK 17")
    
    # Find extracted root
    subdirs = [os.path.join(temp_extract, d) for d in os.listdir(temp_extract) if os.path.isdir(os.path.join(temp_extract, d))]
    if subdirs:
        actual_jdk = subdirs[0]
        if os.path.exists(JDK_DIR):
            shutil.rmtree(JDK_DIR)
        shutil.move(actual_jdk, JDK_DIR)
    shutil.rmtree(temp_extract, ignore_errors=True)
    if os.path.exists(jdk_zip):
        os.remove(jdk_zip)
    print(f"[JDK] JDK 17 ready at {JDK_DIR}")
    return JDK_DIR

def setup_cmdline_tools():
    sdkmanager_bat = os.path.join(SDK_DIR, "cmdline-tools", "latest", "bin", "sdkmanager.bat")
    if os.path.exists(sdkmanager_bat):
        print(f"[SDK Tools] cmdline-tools already setup at {SDK_DIR}")
        return sdkmanager_bat
    
    zip_path = os.path.join(TOOLS_DIR, "cmdline-tools.zip")
    url = "https://dl.google.com/android/repository/commandlinetools-win-11076708_latest.zip"
    download_file(url, zip_path, "Cmdline Tools")
    
    temp_extract = os.path.join(TOOLS_DIR, "cmdline_temp")
    os.makedirs(temp_extract, exist_ok=True)
    extract_zip(zip_path, temp_extract, "Cmdline Tools")
    
    # Android SDK expects: $ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager
    target_latest = os.path.join(SDK_DIR, "cmdline-tools", "latest")
    os.makedirs(os.path.dirname(target_latest), exist_ok=True)
    
    source_dir = os.path.join(temp_extract, "cmdline-tools")
    if os.path.exists(target_latest):
        shutil.rmtree(target_latest)
    shutil.move(source_dir, target_latest)
    shutil.rmtree(temp_extract, ignore_errors=True)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    print(f"[SDK Tools] cmdline-tools ready at {target_latest}")
    return sdkmanager_bat

def install_sdk_packages(sdkmanager_bat, jdk_home):
    env = os.environ.copy()
    env["JAVA_HOME"] = jdk_home
    env["ANDROID_HOME"] = SDK_DIR
    env["ANDROID_SDK_ROOT"] = SDK_DIR
    
    # Accept licenses
    print("[SDK] Accepting licenses...")
    proc = subprocess.Popen(
        [sdkmanager_bat, "--sdk_root=" + SDK_DIR, "--licenses"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env
    )
    # send 'y' repeatedly
    out, _ = proc.communicate(input="y\ny\ny\ny\ny\ny\ny\ny\n")
    
    # Install platform-tools, platforms;android-34, build-tools;34.0.0
    pkgs = ["platform-tools", "platforms;android-34", "build-tools;34.0.0"]
    print(f"[SDK] Installing packages: {pkgs}...")
    cmd = [sdkmanager_bat, "--sdk_root=" + SDK_DIR] + pkgs
    res = subprocess.run(cmd, input="y\n", text=True, capture_output=True, env=env)
    print(res.stdout[-500:] if len(res.stdout) > 500 else res.stdout)
    if res.returncode != 0:
        print("[SDK] Warning / Error during package installation:", res.stderr)
    else:
        print("[SDK] All SDK packages successfully installed!")

def setup_gradle():
    gradle_bat = os.path.join(GRADLE_DIR, "bin", "gradle.bat")
    if os.path.exists(gradle_bat):
        print(f"[Gradle] Gradle 8.7 already setup at {GRADLE_DIR}")
        return gradle_bat
    
    zip_path = os.path.join(TOOLS_DIR, "gradle-8.7-bin.zip")
    url = "https://services.gradle.org/distributions/gradle-8.7-bin.zip"
    download_file(url, zip_path, "Gradle 8.7")
    
    extract_zip(zip_path, TOOLS_DIR, "Gradle 8.7")
    if os.path.exists(zip_path):
        os.remove(zip_path)
    print(f"[Gradle] Gradle ready at {GRADLE_DIR}")
    return gradle_bat

if __name__ == '__main__':
    print("=== Starting Android Build Environment Setup ===")
    jdk = setup_jdk()
    sdkmanager = setup_cmdline_tools()
    install_sdk_packages(sdkmanager, jdk)
    gradle = setup_gradle()
    print("=== Android Build Environment Setup Completed Successfully! ===")
