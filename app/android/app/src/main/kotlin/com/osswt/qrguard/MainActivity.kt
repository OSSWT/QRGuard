package com.osswt.qrguard

import android.content.ContentValues
import android.content.Intent
import android.os.Build
import android.provider.MediaStore
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel
import java.io.IOException

class MainActivity : FlutterActivity() {
    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)
        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "com.osswt.qrguard/external_apps",
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "openTngEWallet" -> {
                    result.success(openInstalledApp("my.com.tngdigital.ewallet"))
                }

                "openHiHive" -> result.success(openInstalledApp("com.slc.hihive.community"))

                else -> result.notImplemented()
            }
        }

        MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger,
            "com.osswt.qrguard/offline_capture",
        ).setMethodCallHandler { call, result ->
            if (call.method != "saveZip") {
                result.notImplemented()
                return@setMethodCallHandler
            }
            val filename = call.argument<String>("filename")
            val bytes = call.argument<ByteArray>("bytes")
            if (filename == null || bytes == null || bytes.isEmpty()) {
                result.error("INVALID_EXPORT", "A filename and non-empty ZIP are required", null)
                return@setMethodCallHandler
            }
            try {
                result.success(saveZipToDownloads(filename, bytes))
            } catch (error: Exception) {
                result.error("SAVE_ZIP_FAILED", error.message, null)
            }
        }
    }

    private fun openInstalledApp(packageName: String): Boolean {
        val launchIntent = packageManager.getLaunchIntentForPackage(packageName)
            ?: return false
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(launchIntent)
        return true
    }

    private fun saveZipToDownloads(requestedName: String, bytes: ByteArray): String {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            throw UnsupportedOperationException(
                "Offline ZIP export requires Android 10 or newer",
            )
        }
        val safeName = requestedName
            .replace(Regex("[^A-Za-z0-9._-]"), "_")
            .take(140)
            .let { if (it.endsWith(".zip", ignoreCase = true)) it else "$it.zip" }
        val values = ContentValues().apply {
            put(MediaStore.Downloads.DISPLAY_NAME, safeName)
            put(MediaStore.Downloads.MIME_TYPE, "application/zip")
            put(MediaStore.Downloads.RELATIVE_PATH, "Download/QRGuard")
            put(MediaStore.Downloads.IS_PENDING, 1)
        }
        val uri = contentResolver.insert(MediaStore.Downloads.EXTERNAL_CONTENT_URI, values)
            ?: throw IOException("Android could not create a Downloads entry")
        try {
            contentResolver.openOutputStream(uri, "w")?.use { output ->
                output.write(bytes)
                output.flush()
            } ?: throw IOException("Android could not open the Downloads entry")
            values.clear()
            values.put(MediaStore.Downloads.IS_PENDING, 0)
            contentResolver.update(uri, values, null, null)
            return uri.toString()
        } catch (error: Exception) {
            contentResolver.delete(uri, null, null)
            throw error
        }
    }
}
