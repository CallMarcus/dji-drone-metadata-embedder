using System.Runtime.InteropServices;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// WebViewSupport is the real default probe behind the VM's
// previewAvailable seam (every VM test pins its own fake). The
// per-platform answers are asserted through the OSPlatform seam so the
// macOS contract is proven on any CI host, not just a Mac: Windows
// depends on the machine's WebView2 runtime, macOS ships WKWebView with
// the OS so the preview is always worth attempting, and Linux (where
// Avalonia's native WebView has no dependable engine) stays on the
// done-card + note degradation path.
public class WebViewSupportTests
{
    [Fact]
    public void On_macos_the_preview_is_always_likely_available()
    {
        Assert.True(WebViewSupport.IsLikelyAvailableOn(OSPlatform.OSX));
    }

    [Fact]
    public void On_linux_the_preview_is_never_likely_available()
    {
        Assert.False(WebViewSupport.IsLikelyAvailableOn(OSPlatform.Linux));
    }

    [Fact]
    public void The_fallback_note_blames_webview2_only_on_windows()
    {
        var windows = WebViewSupport.FallbackNoteOn(OSPlatform.Windows);
        Assert.StartsWith("The map couldn't be previewed inside the app",
            windows);
        Assert.Contains("WebView2", windows);

        // Off Windows the WebView2 sentence would be a lie — macOS ships
        // its engine with the OS, and Linux can't fix it by installing
        // WebView2 either.
        foreach (var platform in new[] { OSPlatform.OSX, OSPlatform.Linux })
        {
            var note = WebViewSupport.FallbackNoteOn(platform);
            Assert.StartsWith("The map couldn't be previewed inside the app",
                note);
            Assert.DoesNotContain("WebView2", note);
            Assert.DoesNotContain("Windows", note);
        }
    }

    [Fact]
    public void The_default_probe_follows_the_current_platform()
    {
        Assert.SkipWhen(OperatingSystem.IsWindows(),
            "On Windows the answer depends on the machine's WebView2 runtime");

        Assert.Equal(
            OperatingSystem.IsMacOS(),
            WebViewSupport.IsLikelyAvailable);
    }
}
