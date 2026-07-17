namespace DjiEmbed.Gui.Tests;

/// <summary>
/// Writes platform fake-CLI scripts that play back canned --progress jsonl
/// streams, so runner/flow tests need no Python.
/// </summary>
internal static class FakeCli
{
    private static bool IsWindows => OperatingSystem.IsWindows();

    internal static string WriteEventStream(string dir,
        IEnumerable<string> stdoutLines, int exitCode = 0,
        string? stderrLine = null, int sleepSeconds = 0)
    {
        if (IsWindows)
        {
            var body = EchoLinesCmd(stdoutLines);
            if (stderrLine is not null) body += $"echo {stderrLine} 1>&2\r\n";
            if (sleepSeconds > 0) body += $"ping -n {sleepSeconds + 1} 127.0.0.1 > nul\r\n";
            body += $"exit /b {exitCode}\r\n";
            return WriteScript(dir, "@echo off\r\n" + body);
        }
        var sh = EchoLinesSh(stdoutLines);
        if (stderrLine is not null) sh += $"echo '{stderrLine}' >&2\n";
        if (sleepSeconds > 0) sh += $"sleep {sleepSeconds}\n";
        sh += $"exit {exitCode}\n";
        return WriteScript(dir, "#!/bin/sh\n" + sh);
    }

    /// <summary>
    /// A fake CLI that branches on its first argument (the subcommand), so
    /// one script can answer both the flightmap and photomap invocation.
    /// </summary>
    internal static string WritePerCommand(string dir,
        IReadOnlyDictionary<string, (string[] Lines, int ExitCode)> commands)
    {
        if (IsWindows)
        {
            var body = "@echo off\r\n";
            foreach (var (cmd, spec) in commands)
            {
                body += $"if \"%1\"==\"{cmd}\" (\r\n"
                    + EchoLinesCmd(spec.Lines)
                    + $"exit /b {spec.ExitCode}\r\n)\r\n";
            }
            body += "exit /b 99\r\n";
            return WriteScript(dir, body);
        }
        var sh = "#!/bin/sh\ncase \"$1\" in\n";
        foreach (var (cmd, spec) in commands)
        {
            sh += $"{cmd})\n" + EchoLinesSh(spec.Lines) + $"exit {spec.ExitCode}\n;;\n";
        }
        sh += "esac\nexit 99\n";
        return WriteScript(dir, sh);
    }

    /// <summary>
    /// A fake CLI that appends its argv to <paramref name="argsFile"/>, then
    /// plays back <paramref name="stdoutLines"/> and exits 0.
    /// </summary>
    internal static string WriteArgsRecorder(string dir, string argsFile,
        IEnumerable<string> stdoutLines)
    {
        if (IsWindows)
        {
            return WriteScript(dir, "@echo off\r\n"
                + $"echo %* >> \"{argsFile}\"\r\n"
                + EchoLinesCmd(stdoutLines) + "exit /b 0\r\n");
        }
        return WriteScript(dir, "#!/bin/sh\n"
            + $"echo \"$@\" >> '{argsFile}'\n"
            + EchoLinesSh(stdoutLines) + "exit 0\n");
    }

    private static string EchoLinesCmd(IEnumerable<string> lines) =>
        string.Concat(lines.Select(l =>
            "echo " + l.Replace("\"", "\"\"") + "\r\n"));

    private static string EchoLinesSh(IEnumerable<string> lines) =>
        string.Concat(lines.Select(l =>
            "echo '" + l.Replace("'", "'\\''") + "'\n"));

    internal static string WriteScript(string dir, string body)
    {
        var path = Path.Combine(dir,
            "fake-cli-" + Guid.NewGuid().ToString("N")[..8]
            + (IsWindows ? ".cmd" : ".sh"));
        File.WriteAllText(path, body);
        if (!OperatingSystem.IsWindows())
        {
            File.SetUnixFileMode(path,
                UnixFileMode.UserRead | UnixFileMode.UserWrite
                | UnixFileMode.UserExecute);
        }
        return path;
    }
}
