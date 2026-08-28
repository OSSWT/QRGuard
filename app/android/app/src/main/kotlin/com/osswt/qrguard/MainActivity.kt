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
            "com.osswt.qrguard/external_payment_apps",
        ).setMethodCallHandler { call, result ->
            when (call.method) {
                "openTngEWallet" -> {
                    val launchIntent = packageManager
                        .getLaunchIntentForPackage("my.com.tngdigital.ewallet")
                    if (launchIntent == null) {
                        result.success(false)
                    } else {
                        launchIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        startActivity(launchIntent)
                        result.success(true)
                    }
                }

                else -> result.notImplemented()
            }
        }
    }
}
