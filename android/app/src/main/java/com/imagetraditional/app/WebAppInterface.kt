package com.imagetraditional.app

import android.content.Context
import android.webkit.JavascriptInterface
import android.widget.Toast

/**
 * JavaScript interface bridge between Image Traditional web app and native Android shell.
 */
class WebAppInterface(private val context: Context) {

    @JavascriptInterface
    fun isNativeApp(): Boolean {
        return true
    }

    @JavascriptInterface
    fun getAppVersion(): String {
        return "1.0.0"
    }

    @JavascriptInterface
    fun showToast(message: String) {
        Toast.makeText(context, message, Toast.LENGTH_SHORT).show()
    }
}
