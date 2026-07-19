using System;
using System.Runtime.Versioning;
using Microsoft.Win32;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Whether the inline map preview is worth attempting on this machine:
/// Windows with the WebView2 runtime actually installed. The app ships
/// for Windows, where WebView2 is preinstalled from Windows 11 on — but
/// on a runtime-less Windows 10 the control attaches silently and stays
/// blank, so the OS check alone isn't enough; probing the runtime's
/// registry footprint sends those machines down the done-card + note
/// path instead, per the GUI 2.0 spec's degradation rule. A machine that
/// passes this probe but still lacks a usable engine is caught by the
/// try/catch around the control itself.
/// </summary>
public static class WebViewSupport
{
    public static bool IsLikelyAvailable =>
        OperatingSystem.IsWindows() && HasWebView2Runtime();

    // Documented runtime detection: the EdgeUpdate client key for the WebView2 runtime
    // ({F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}) with a plausible "pv" version value.
    // https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution#detect-if-a-suitable-webview2-runtime-is-already-installed
    [SupportedOSPlatform("windows")]
    private static bool HasWebView2Runtime()
    {
        const string wow64 = @"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
        const string plain = @"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}";
        try
        {
            return HasPlausiblePv(Registry.LocalMachine, wow64)
                || HasPlausiblePv(Registry.LocalMachine, plain)
                || HasPlausiblePv(Registry.CurrentUser, plain);
        }
        catch
        {
            // Unreadable registry: assume no runtime — the degraded path works everywhere,
            // a silently blank preview pane does not.
            return false;
        }
    }

    [SupportedOSPlatform("windows")]
    private static bool HasPlausiblePv(RegistryKey hive, string path)
    {
        using var key = hive.OpenSubKey(path);
        return key?.GetValue("pv") is string pv && pv.Length > 0 && pv != "0.0.0.0";
    }
}
