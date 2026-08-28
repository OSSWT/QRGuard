package com.osswt.qrguard

import android.content.Intent
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

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
    }

    private fun openInstalledApp(packageName: String): Boolean {
        val launchIntent = packageManager.getLaunchIntentForPackage(packageName)
            ?: return false
        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(launchIntent)
        return true
    }
}
