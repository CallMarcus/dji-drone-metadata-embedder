using System.Reflection;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// The version the running build was stamped with (release workflows pass
/// <c>-p:Version=X.Y.Z</c> at publish). Shown in the main window title so
/// a field report can name its version from any screenshot — a tester
/// spent three messages unable to say which build he was running (#532).
/// </summary>
public static class AppVersion
{
    public static string WindowTitle => TitleFor(Current);

    public static string TitleFor(string? version) => version is null
        ? "DJI Metadata Embedder"
        : "DJI Metadata Embedder v" + version;

    /// <summary>The stamped version, or null for an unstamped dev build —
    /// where showing the SDK's default would mislead exactly the reports
    /// the title exists for.</summary>
    public static string? Current => Normalize(
        Assembly.GetExecutingAssembly()
            .GetCustomAttribute<AssemblyInformationalVersionAttribute>()
            ?.InformationalVersion);

    /// <summary>"2.11.0+abc123" → "2.11.0" (SourceLink appends the commit
    /// as build metadata); blank or the SDK default "1.0.0" → null.</summary>
    public static string? Normalize(string? informational)
    {
        if (string.IsNullOrWhiteSpace(informational))
        {
            return null;
        }
        var plus = informational.IndexOf('+');
        var version = plus >= 0 ? informational[..plus] : informational;
        return version == "1.0.0" ? null : version;
    }
}
