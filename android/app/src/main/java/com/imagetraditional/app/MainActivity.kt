package com.imagetraditional.app

import android.annotation.SuppressLint
import android.app.DownloadManager
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.view.View
import android.webkit.CookieManager
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.ActivityResultLauncher
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.swiperefreshlayout.widget.SwipeRefreshLayout

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var swipeRefresh: SwipeRefreshLayout
    private lateinit var progressBar: ProgressBar
    private lateinit var offlineContainer: LinearLayout
    private lateinit var offlineTitle: TextView
    private lateinit var offlineMessage: TextView
    private lateinit var btnRetry: Button
    private lateinit var btnOfflineCatalogue: Button

    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null
    private lateinit var fileChooserLauncher: ActivityResultLauncher<Intent>

    private var doubleBackToExitPressedOnce = false
    private val mainHandler = Handler(Looper.getMainLooper())

    // Lazy initialization ensures connectivityManager is never accessed uninitialized
    private val connectivityManager: ConnectivityManager by lazy {
        getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    }
    private var networkCallback: ConnectivityManager.NetworkCallback? = null

    // Production entry point route (/app)
    private val defaultAppUrl: String by lazy {
        getString(R.string.app_url)
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        // Transition from Splash theme to standard app theme
        setTheme(R.style.Theme_ImageTraditional)
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        try {
            initViews()
            initFileChooser()
            initNetworkMonitoring()
            initWebView()
            initBackNavigation()

            // Load entry point
            if (savedInstanceState != null) {
                webView.restoreState(savedInstanceState)
            } else {
                loadInitialUrl()
            }
        } catch (e: Exception) {
            e.printStackTrace()
            Toast.makeText(this, "Starting Image Traditional...", Toast.LENGTH_SHORT).show()
        }
    }

    private fun initViews() {
        webView = findViewById(R.id.webView)
        swipeRefresh = findViewById(R.id.swipeRefresh)
        progressBar = findViewById(R.id.progressBar)
        offlineContainer = findViewById(R.id.offlineContainer)
        offlineTitle = findViewById(R.id.offlineTitle)
        offlineMessage = findViewById(R.id.offlineMessage)
        btnRetry = findViewById(R.id.btnRetry)
        btnOfflineCatalogue = findViewById(R.id.btnOfflineCatalogue)

        // Configure pull to refresh
        swipeRefresh.setColorSchemeResources(
            R.color.brand_gold,
            R.color.brand_gold_dark,
            R.color.brand_gold_light
        )
        swipeRefresh.setProgressBackgroundColorSchemeResource(R.color.brand_surface)
        swipeRefresh.setOnRefreshListener {
            if (isNetworkAvailable()) {
                webView.reload()
            } else {
                swipeRefresh.isRefreshing = false
                Toast.makeText(this, "Operating offline", Toast.LENGTH_SHORT).show()
            }
        }

        // Crash-safe scroll check for SwipeRefreshLayout with WebView
        swipeRefresh.setOnChildScrollUpCallback { _, _ ->
            webView.scrollY > 0
        }

        btnRetry.setOnClickListener {
            offlineContainer.visibility = View.GONE
            webView.visibility = View.VISIBLE
            webView.reload()
        }

        btnOfflineCatalogue.setOnClickListener {
            offlineContainer.visibility = View.GONE
            webView.visibility = View.VISIBLE
            // Navigate to public catalogue which operates with Service Worker / Cache
            val catalogueUrl = Uri.parse(defaultAppUrl).buildUpon().path("/kediya").build().toString()
            webView.loadUrl(catalogueUrl)
        }
    }

    private fun initFileChooser() {
        fileChooserLauncher = registerForActivityResult(
            ActivityResultContracts.StartActivityForResult()
        ) { result ->
            val data = result.data
            val results: Array<Uri>? = when {
                result.resultCode == RESULT_OK && data != null -> {
                    val clipData = data.clipData
                    val dataString = data.dataString
                    when {
                        clipData != null -> {
                            Array(clipData.itemCount) { i -> clipData.getItemAt(i).uri }
                        }
                        dataString != null -> {
                            arrayOf(Uri.parse(dataString))
                        }
                        else -> null
                    }
                }
                else -> null
            }
            fileChooserCallback?.onReceiveValue(results)
            fileChooserCallback = null
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private fun initWebView() {
        val settings = webView.settings

        // 1. JavaScript & DOM / Database Storage
        settings.javaScriptEnabled = true
        settings.domStorageEnabled = true
        settings.databaseEnabled = true

        // 2. Viewport & Scaling (Native app look & feel)
        settings.useWideViewPort = true
        settings.loadWithOverviewMode = true
        settings.setSupportZoom(true)
        settings.builtInZoomControls = true
        settings.displayZoomControls = false

        // 3. Security Settings (Strict HTTPS)
        settings.allowFileAccess = false
        settings.allowContentAccess = false
        settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW

        // 4. Custom User-Agent tag (Appended so server can identify APK requests)
        val originalUa = settings.userAgentString
        settings.userAgentString = "$originalUa ImageTraditionalApp/1.0 (Android)"

        // 5. Cookie & Session Management
        val cookieManager = CookieManager.getInstance()
        cookieManager.setAcceptCookie(true)
        cookieManager.setAcceptThirdPartyCookies(webView, true)

        // 6. Native JS Bridge
        webView.addJavascriptInterface(WebAppInterface(this), "ImageTraditionalAndroid")

        // 7. Cache Mode based on initial connection
        updateCacheMode(isNetworkAvailable())

        // 8. WebView Client
        webView.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?
            ): Boolean {
                val uri = request?.url ?: return false
                return handleUrlNavigation(uri)
            }

            @Deprecated("Deprecated in Java")
            override fun shouldOverrideUrlLoading(view: WebView?, url: String?): Boolean {
                if (url == null) return false
                return handleUrlNavigation(Uri.parse(url))
            }

            override fun onPageStarted(view: WebView?, url: String?, favicon: Bitmap?) {
                super.onPageStarted(view, url, favicon)
                progressBar.visibility = View.VISIBLE
                progressBar.progress = 15
                offlineContainer.visibility = View.GONE
            }

            override fun onPageFinished(view: WebView?, url: String?) {
                super.onPageFinished(view, url)
                progressBar.visibility = View.GONE
                swipeRefresh.isRefreshing = false

                // Flush session cookies to SQLite persistent disk storage
                try {
                    CookieManager.getInstance().flush()
                } catch (e: Exception) {
                    e.printStackTrace()
                }
            }

            override fun onReceivedHttpError(
                view: WebView?,
                request: WebResourceRequest?,
                errorResponse: WebResourceResponse?
            ) {
                super.onReceivedHttpError(view, request, errorResponse)
                if (request?.isForMainFrame == true) {
                    val statusCode = errorResponse?.statusCode ?: 0
                    val url = request.url.toString()
                    // Fallback to /login if /app returns 404
                    if (statusCode == 404 && url.endsWith("/app")) {
                        val loginUrl = Uri.parse(defaultAppUrl).buildUpon().path("/login").build().toString()
                        view?.loadUrl(loginUrl)
                    }
                }
            }

            override fun onReceivedError(
                view: WebView?,
                request: WebResourceRequest?,
                error: WebResourceError?
            ) {
                super.onReceivedError(view, request, error)

                // Only handle main frame navigation errors
                if (request?.isForMainFrame == true) {
                    val url = request.url.toString()
                    val isAdminRoute = url.contains("/admin") ||
                            url.contains("/login") ||
                            url.contains("/app") ||
                            url.contains("/navaratri") ||
                            url.contains("/fancy") ||
                            url.contains("/book") ||
                            url.contains("/modify") ||
                            url.contains("/delete") ||
                            url.contains("/calendar")

                    if (!isNetworkAvailable()) {
                        if (isAdminRoute) {
                            // Show clear, styled admin offline warning
                            offlineTitle.text = getString(R.string.offline_title)
                            offlineMessage.text = getString(R.string.offline_admin_msg)
                            offlineContainer.visibility = View.VISIBLE
                            webView.visibility = View.GONE
                        }
                    }
                }
            }
        }

        // 9. WebChromeClient
        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                super.onProgressChanged(view, newProgress)
                progressBar.progress = newProgress
                if (newProgress >= 100) {
                    progressBar.visibility = View.GONE
                } else {
                    progressBar.visibility = View.VISIBLE
                }
            }

            override fun onShowFileChooser(
                webView: WebView?,
                filePathCallback: ValueCallback<Array<Uri>>?,
                fileChooserParams: FileChooserParams?
            ): Boolean {
                fileChooserCallback?.onReceiveValue(null)
                fileChooserCallback = filePathCallback

                return try {
                    val intent = fileChooserParams?.createIntent() ?: Intent(Intent.ACTION_GET_CONTENT).apply {
                        type = "image/*"
                        addCategory(Intent.CATEGORY_OPENABLE)
                    }
                    fileChooserLauncher.launch(intent)
                    true
                } catch (e: Exception) {
                    fileChooserCallback = null
                    false
                }
            }
        }

        // 10. File Downloads Handling (Invoices, PDF bills, APK downloads)
        webView.setDownloadListener { url, _, _, _, _ ->
            handleDownload(url)
        }
    }

    private fun handleUrlNavigation(uri: Uri): Boolean {
        val scheme = uri.scheme?.lowercase() ?: ""

        // Handle External Intents (tel, mailto, maps, whatsapp, instagram, etc.)
        if (isExternalScheme(uri)) {
            return handleExternalIntent(uri)
        }

        // Internal URL within Image Traditional domain -> MUST LOAD IN WEBVIEW!
        if (isInternalDomain(uri)) {
            return false
        }

        // Other non-HTTP schemes
        if (scheme != "http" && scheme != "https") {
            return handleExternalIntent(uri)
        }

        // External domain -> open in external browser
        return try {
            val intent = Intent(Intent.ACTION_VIEW, uri)
            startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun isExternalScheme(uri: Uri): Boolean {
        val scheme = uri.scheme?.lowercase() ?: ""
        return scheme in listOf("tel", "mailto", "sms", "whatsapp", "geo") ||
                uri.host?.contains("instagram.com") == true ||
                uri.host?.contains("maps.app.goo.gl") == true ||
                uri.host?.contains("maps.google.com") == true
    }

    private fun handleExternalIntent(uri: Uri): Boolean {
        return try {
            val intent = Intent(Intent.ACTION_VIEW, uri)
            startActivity(intent)
            true
        } catch (e: Exception) {
            Toast.makeText(this, "Application not found to handle action", Toast.LENGTH_SHORT).show()
            false
        }
    }

    private fun isInternalDomain(uri: Uri): Boolean {
        val host = uri.host?.lowercase() ?: ""
        // Relative or path URLs within the app are internal
        if (host.isEmpty()) return true

        val defaultHost = Uri.parse(defaultAppUrl).host?.lowercase() ?: "image-traditional.onrender.com"
        return host == defaultHost ||
                host.contains("image-traditional") ||
                host.contains("onrender.com") ||
                host == "localhost" ||
                host == "127.0.0.1" ||
                host == "10.0.2.2"
    }

    private fun handleDownload(url: String) {
        try {
            val request = DownloadManager.Request(Uri.parse(url))
            val cookie = CookieManager.getInstance().getCookie(url)
            if (cookie != null) {
                request.addRequestHeader("Cookie", cookie)
            }
            request.addRequestHeader("User-Agent", webView.settings.userAgentString)
            request.setDescription(getString(R.string.download_started))
            request.setTitle("Image Traditional Document")
            request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
            request.setDestinationInExternalPublicDir(
                Environment.DIRECTORY_DOWNLOADS,
                "ImageTraditional_" + System.currentTimeMillis() + ".pdf"
            )

            val dm = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
            dm.enqueue(request)
            Toast.makeText(this, getString(R.string.download_started), Toast.LENGTH_SHORT).show()
        } catch (e: Exception) {
            // Fallback to browser download intent
            try {
                val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                startActivity(intent)
            } catch (ex: Exception) {
                Toast.makeText(this, "Download failed: ${e.localizedMessage}", Toast.LENGTH_SHORT).show()
            }
        }
    }

    private fun initBackNavigation() {
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (offlineContainer.visibility == View.VISIBLE) {
                    offlineContainer.visibility = View.GONE
                    webView.visibility = View.VISIBLE
                    return
                }

                val history = webView.copyBackForwardList()
                val currentIndex = history.currentIndex

                if (currentIndex <= 0) {
                    handleDoubleBackExit()
                    return
                }

                val currentUrl = history.getItemAtIndex(currentIndex)?.url ?: ""

                // 1. If currently on /login or /app: do not loop back into /app redirect; prompt exit
                if (currentUrl.contains("/login") || currentUrl.endsWith("/app")) {
                    handleDoubleBackExit()
                    return
                }

                // 2. If currently on /admin: check if prior pages contain valid browsing pages, otherwise exit
                if (currentUrl.contains("/admin")) {
                    var targetStep = 0
                    for (i in (currentIndex - 1) downTo 0) {
                        val prevUrl = history.getItemAtIndex(i)?.url ?: ""
                        if (!prevUrl.contains("/app") && !prevUrl.contains("/login")) {
                            targetStep = i - currentIndex
                            break
                        }
                    }
                    if (targetStep < 0) {
                        webView.goBackOrForward(targetStep)
                    } else {
                        handleDoubleBackExit()
                    }
                    return
                }

                // 3. For any other page: find the closest previous page that is not /app
                var targetStep = 0
                for (i in (currentIndex - 1) downTo 0) {
                    val prevUrl = history.getItemAtIndex(i)?.url ?: ""
                    if (prevUrl.endsWith("/app") || prevUrl.contains("/app?")) {
                        continue
                    }
                    targetStep = i - currentIndex
                    break
                }

                if (targetStep < 0) {
                    webView.goBackOrForward(targetStep)
                } else {
                    handleDoubleBackExit()
                }
            }
        })
    }

    private fun handleDoubleBackExit() {
        if (doubleBackToExitPressedOnce) {
            finish()
            return
        }

        doubleBackToExitPressedOnce = true
        Toast.makeText(this, getString(R.string.exit_prompt), Toast.LENGTH_SHORT).show()

        mainHandler.postDelayed({
            doubleBackToExitPressedOnce = false
        }, 2000)
    }

    private fun initNetworkMonitoring() {
        try {
            val callback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    runOnUiThread {
                        updateCacheMode(true)
                        if (::offlineContainer.isInitialized && offlineContainer.visibility == View.VISIBLE) {
                            offlineContainer.visibility = View.GONE
                            if (::webView.isInitialized) {
                                webView.visibility = View.VISIBLE
                                webView.reload()
                            }
                        }
                    }
                }

                override fun onLost(network: Network) {
                    runOnUiThread {
                        updateCacheMode(false)
                    }
                }
            }
            networkCallback = callback

            val request = NetworkRequest.Builder()
                .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .build()
            connectivityManager.registerNetworkCallback(request, callback)
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    private fun updateCacheMode(online: Boolean) {
        if (::webView.isInitialized) {
            webView.settings.cacheMode = if (online) {
                WebSettings.LOAD_DEFAULT
            } else {
                WebSettings.LOAD_CACHE_ELSE_NETWORK
            }
        }
    }

    private fun isNetworkAvailable(): Boolean {
        return try {
            val activeNetwork = connectivityManager.activeNetwork ?: return false
            val capabilities = connectivityManager.getNetworkCapabilities(activeNetwork) ?: return false
            capabilities.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
        } catch (e: Exception) {
            true // Safe optimistic fallback
        }
    }

    private fun loadInitialUrl() {
        webView.loadUrl(defaultAppUrl)
    }

    override fun onPause() {
        super.onPause()
        try {
            CookieManager.getInstance().flush()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    override fun onStop() {
        super.onStop()
        try {
            CookieManager.getInstance().flush()
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    override fun onSaveInstanceState(outState: Bundle) {
        super.onSaveInstanceState(outState)
        try {
            if (::webView.isInitialized) {
                webView.saveState(outState)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }

    override fun onDestroy() {
        super.onDestroy()
        try {
            CookieManager.getInstance().flush()
        } catch (e: Exception) {
            e.printStackTrace()
        }
        try {
            networkCallback?.let { callback ->
                connectivityManager.unregisterNetworkCallback(callback)
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
        try {
            if (::webView.isInitialized) {
                webView.destroy()
            }
        } catch (e: Exception) {
            e.printStackTrace()
        }
    }
}
