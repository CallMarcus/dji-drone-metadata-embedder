using System;
using System.Runtime.InteropServices;
using System.Runtime.Versioning;
using Microsoft.Win32;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Whether the inline map preview is worth attempting on this machine.
/// Per platform: Windows needs the WebView2 runtime actually installed —
/// it is preinstalled from Windows 11 on, but on a runtime-less Windows
/// 10 the control attaches silently and stays blank, so the OS check
/// alone isn't enough; probing the runtime's registry footprint sends
/// those machines down the done-card + note path instead, per the GUI
/// 2.0 spec's degradation rule. macOS ships WKWebView with the OS, so
/// the preview is always worth attempting there. Linux has no dependable
/// native WebView engine (#360), so it stays on the degraded path. A
/// machine that passes this probe but still lacks a usable engine is
/// caught by the try/catch around the control itself.
/// </summary>
public static class WebViewSupport
{
    public static bool IsLikelyAvailable =>
        OperatingSystem.IsWindows()
            ? HasWebView2Runtime()
            : IsLikelyAvailableOn(Platforms.Current);

    /// <summary>The done-card note shown when the preview pane stays
    /// blank — Open still works, so stay calm and say so. Only Windows
    /// gets the WebView2 sentence: macOS ships its engine with the OS,
    /// and Linux can't fix it by installing WebView2 either.</summary>
    public static string FallbackNote => FallbackNoteOn(Platforms.Current);

    internal static string FallbackNoteOn(OSPlatform platform)
    {
        const string common = "The map couldn't be previewed inside the app"
            + " — Open shows it in your browser instead.";
        return platform == OSPlatform.Windows
            ? common + " Inline preview needs Microsoft Edge WebView2,"
                + " which comes preinstalled from Windows 11 on."
            : common;
    }

    /// <summary>The per-platform answer, minus the Windows registry
    /// probe (which only the public property runs, on Windows itself) —
    /// a seam so the macOS and Linux contracts are testable on any CI
    /// host.</summary>
    internal static bool IsLikelyAvailableOn(OSPlatform platform) =>
        platform == OSPlatform.OSX;

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
