# Keep JavascriptInterface methods
-keepclassmembers class * {
    @android.webkit.JavascriptInterface <methods>;
}

-keep class com.imagetraditional.app.WebAppInterface { *; }
