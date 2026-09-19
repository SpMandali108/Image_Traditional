package com.imagetraditional.app

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.LayoutInflater
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.core.content.FileProvider
import com.google.android.material.dialog.MaterialAlertDialogBuilder
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/**
 * Manages in-app automated OTA updates for Image Traditional APK.
 * Periodically checks /api/app/version on the live server and prompts the user
 * to download and install updates in-place without manual file navigation.
 */
class AppUpdateManager(private val activity: Activity) {

    private val mainHandler = Handler(Looper.getMainLooper())
    private var isChecking = false
    private var lastCheckTime: Long = 0

    companion object {
        private const val CHECK_INTERVAL_MS = 15 * 60 * 1000 // Check at most once every 15 minutes
        private const val TIMEOUT_MS = 6000
    }

    fun checkForUpdatesSilently(versionApiUrl: String) {
        val now = System.currentTimeMillis()
        if (isChecking || (now - lastCheckTime < CHECK_INTERVAL_MS)) {
            return
        }

        isChecking = true
        lastCheckTime = now

        thread(name = "AppUpdateChecker") {
            try {
                val url = URL(versionApiUrl)
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    connectTimeout = TIMEOUT_MS
                    readTimeout = TIMEOUT_MS
                    requestMethod = "GET"
                    setRequestProperty("Accept", "application/json")
                    setRequestProperty("User-Agent", "ImageTraditionalApp/1.0 (Android AutoUpdater)")
                }

                if (conn.responseCode == 200) {
                    val responseText = conn.inputStream.bufferedReader().use { it.readText() }
                    val json = JSONObject(responseText)
                    val serverVersionCode = json.optLong("version_code", 0)
                    val serverVersionName = json.optString("version_name", "1.0.0")
                    var downloadUrl = json.optString("apk_url", "/download/ImageTraditional.apk")
                    val releaseNotes = json.optString("release_notes", "A new version of Image Traditional is available.")
                    val isMandatory = json.optBoolean("mandatory", false)

                    // Resolve relative URLs to full base URL
                    if (downloadUrl.startsWith("/")) {
                        val base = Uri.parse(versionApiUrl)
                        downloadUrl = "${base.scheme}://${base.host}$downloadUrl"
                    }

                    val currentVersionCode = getCurrentVersionCode(activity)

                    if (serverVersionCode > currentVersionCode) {
                        mainHandler.post {
                            if (!activity.isFinishing && !activity.isDestroyed) {
                                promptUserToUpdate(serverVersionName, downloadUrl, releaseNotes, isMandatory)
                            }
                        }
                    }
                }
            } catch (e: Exception) {
                // Fail silently - updates should never disrupt the core app flow
                e.printStackTrace()
            } finally {
                isChecking = false
            }
        }
    }

    private fun getCurrentVersionCode(context: Context): Long {
        return try {
            val packageInfo = context.packageManager.getPackageInfo(context.packageName, 0)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                packageInfo.longVersionCode
            } else {
                @Suppress("DEPRECATION")
                packageInfo.versionCode.toLong()
            }
        } catch (e: Exception) {
            1L
        }
    }

    private fun promptUserToUpdate(
        versionName: String,
        downloadUrl: String,
        notes: String,
        mandatory: Boolean
    ) {
        val builder = MaterialAlertDialogBuilder(activity, R.style.Theme_ImageTraditional)
            .setTitle("🚀 Update Available (v$versionName)")
            .setMessage("$notes\n\nWould you like to install the update now?")
            .setPositiveButton("Update Now") { dialog, _ ->
                dialog.dismiss()
                startDownloadAndInstall(downloadUrl)
            }

        if (!mandatory) {
            builder.setNegativeButton("Later") { dialog, _ ->
                dialog.dismiss()
            }
        } else {
            builder.setCancelable(false)
        }

        builder.show()
    }

    private fun startDownloadAndInstall(downloadUrl: String) {
        // Build Progress Dialog
        val dialogView = LayoutInflater.from(activity).inflate(
            android.R.layout.simple_list_item_2, null
        )
        val titleView = dialogView.findViewById<TextView>(android.R.id.text1)
        val progressTextView = dialogView.findViewById<TextView>(android.R.id.text2)

        titleView.text = "Downloading Update..."
        progressTextView.text = "Preparing download..."

        val progressBar = ProgressBar(activity, null, android.R.attr.progressBarStyleHorizontal).apply {
            isIndeterminate = false
            max = 100
            progress = 0
            setPadding(40, 20, 40, 30)
        }

        val container = android.widget.LinearLayout(activity).apply {
            orientation = android.widget.LinearLayout.VERTICAL
            addView(dialogView)
            addView(progressBar)
        }

        val progressDialog = AlertDialog.Builder(activity)
            .setView(container)
            .setCancelable(false)
            .create()

        progressDialog.show()

        thread(name = "ApkDownloader") {
            var input: java.io.InputStream? = null
            var output: FileOutputStream? = null
            var conn: HttpURLConnection? = null

            try {
                val url = URL(downloadUrl)
                conn = (url.openConnection() as HttpURLConnection).apply {
                    connectTimeout = 10000
                    readTimeout = 20000
                    requestMethod = "GET"
                    setRequestProperty("User-Agent", "ImageTraditionalApp/1.0 (Android AutoUpdater)")
                }

                val fileLength = conn.contentLength
                input = conn.inputStream

                val storageDir = activity.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS) ?: activity.cacheDir
                val apkFile = File(storageDir, "ImageTraditional_update.apk")
                if (apkFile.exists()) {
                    apkFile.delete()
                }

                output = FileOutputStream(apkFile)

                val data = ByteArray(4096)
                var total: Long = 0
                var count: Int

                while (input.read(data).also { count = it } != -1) {
                    total += count
                    if (fileLength > 0) {
                        val progressPercent = ((total * 100) / fileLength).toInt()
                        mainHandler.post {
                            progressBar.progress = progressPercent
                            progressTextView.text = "$progressPercent% downloaded (${total / 1024} KB / ${fileLength / 1024} KB)"
                        }
                    }
                    output.write(data, 0, count)
                }

                output.flush()

                mainHandler.post {
                    progressDialog.dismiss()
                    triggerInstallation(apkFile)
                }

            } catch (e: Exception) {
                e.printStackTrace()
                mainHandler.post {
                    progressDialog.dismiss()
                    Toast.makeText(activity, "Download failed: ${e.localizedMessage}", Toast.LENGTH_LONG).show()
                }
            } finally {
                try {
                    output?.close()
                    input?.close()
                    conn?.disconnect()
                } catch (ignored: Exception) {}
            }
        }
    }

    private fun triggerInstallation(apkFile: File) {
        if (!apkFile.exists()) {
            Toast.makeText(activity, "Update package not found", Toast.LENGTH_SHORT).show()
            return
        }

        // On Android 8.0+ (Oreo, API 26+), verify install unknown apps permission
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            if (!activity.packageManager.canRequestPackageInstalls()) {
                Toast.makeText(activity, "Please allow permission to install updates", Toast.LENGTH_LONG).show()
                val settingsIntent = Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES).apply {
                    data = Uri.parse("package:${activity.packageName}")
                }
                activity.startActivity(settingsIntent)
            }
        }

        try {
            val apkUri = FileProvider.getUriForFile(
                activity,
                "${activity.packageName}.fileprovider",
                apkFile
            )

            val installIntent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(apkUri, "application/vnd.android.package-archive")
                addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }

            activity.startActivity(installIntent)
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(activity, "Unable to launch installer: ${e.localizedMessage}", Toast.LENGTH_LONG).show()
        }
    }
}
