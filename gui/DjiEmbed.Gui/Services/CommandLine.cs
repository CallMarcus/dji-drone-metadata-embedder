using System.Collections.Generic;
using System.Linq;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Renders an argv as a single command line for the CLI transparency strip
/// (GUI 2.0 spec, M3a). This is <b>best-effort display quoting</b> — for
/// readability and copy convenience only — and is <b>not shell-safe</b>: an
/// argument is double-quoted only when empty or containing whitespace, and
/// nothing else is escaped. It does not neutralise shell metacharacters, so
/// it must never be used to build a command that is actually executed. Real
/// execution goes through <see cref="System.Diagnostics.ProcessStartInfo"/>'s
/// <c>ArgumentList</c>, which escapes each argument independently.
/// </summary>
public static class CommandLine
{
    public static string Format(string program, IReadOnlyList<string> args)
    {
        var parts = new List<string>(args.Count + 1) { program };
        parts.AddRange(args.Select(Quote));
        return string.Join(' ', parts);
    }

    private static string Quote(string arg) =>
        arg.Length == 0 || arg.Any(char.IsWhiteSpace) ? $"\"{arg}\"" : arg;
}
