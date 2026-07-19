using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// WebViewSupport is the real default probe behind the VM's
// previewAvailable seam (every VM test pins its own fake) — off Windows
// there is never a WebView2 runtime, so the probe must say no and send
// the app down the done-card + note degradation path.
public class WebViewSupportTests
{
    [Fact]
    public void Off_windows_the_preview_is_never_likely_available()
    {
        Assert.SkipWhen(OperatingSystem.IsWindows(),
            "On Windows the answer depends on the machine's WebView2 runtime");

        Assert.False(WebViewSupport.IsLikelyAvailable);
    }
}
