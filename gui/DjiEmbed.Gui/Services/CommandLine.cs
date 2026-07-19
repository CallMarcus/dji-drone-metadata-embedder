using System.Collections.Generic;
using System.Linq;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Renders an argv as a single copy-pasteable command line for the CLI
/// transparency strip (GUI 2.0 spec, M3a). Minimal quoting: an argument is
/// double-quoted only when empty or containing whitespace. Paths cannot
/// contain a literal double-quote on Windows or POSIX, so no escaping of
/// embedded quotes is needed.
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
