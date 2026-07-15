using System.Runtime.InteropServices;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

// The runner is tested against fake CLI scripts so no Python is needed:
// each test writes a platform script that plays back a canned event stream.
public class DjiEmbedRunnerTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-runner-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string WriteFakeCli(IEnumerable<string> stdoutLines,
        int exitCode = 0, string? stderrLine = null, int sleepSeconds = 0)
    {
        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            var cmd = Path.Combine(_dir, "fake-cli.cmd");
            var body = "@echo off\r\n" + string.Join("\r\n",
                stdoutLines.Select(l => "echo " + l.Replace("\"", "\"\""))); // best effort
            if (stderrLine is not null) body += $"\r\necho {stderrLine} 1>&2";
            if (sleepSeconds > 0) body += $"\r\nping -n {sleepSeconds + 1} 127.0.0.1 > nul";
            body += $"\r\nexit /b {exitCode}\r\n";
            File.WriteAllText(cmd, body);
            return cmd;
        }
        var sh = Path.Combine(_dir, "fake-cli.sh");
        var lines = string.Join("\n",
            stdoutLines.Select(l => "echo '" + l.Replace("'", "'\\''") + "'"));
        if (stderrLine is not null) lines += $"\necho '{stderrLine}' >&2";
        if (sleepSeconds > 0) lines += $"\nsleep {sleepSeconds}";
        File.WriteAllText(sh, "#!/bin/sh\n" + lines + $"\nexit {exitCode}\n");
        File.SetUnixFileMode(sh,
            UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
        return sh;
    }

    private static readonly string[] HappyStream =
    [
        """{"v": 1, "event": "start", "command": "flightmap", "total": 2}""",
        """{"v": 1, "event": "progress", "current": 1, "total": 2, "item": "a.SRT"}""",
        """{"v": 1, "event": "progress", "current": 2, "total": 2, "item": "b.SRT"}""",
        """{"v": 1, "event": "result", "ok": true, "outputs": ["map.html"], "summary": {"flights": 2}}""",
    ];

    [Fact]
    public async Task Happy_path_reports_events_and_terminal_result()
    {
        var cli = WriteFakeCli(HappyStream);
        var seen = new List<ProgressEvent>();
        var result = await new DjiEmbedRunner().RunAsync(
            cli, ["flightmap", "/some/dir"],
            new Progress<ProgressEvent>(seen.Add));

        Assert.Equal(0, result.ExitCode);
        Assert.True(result.Success);
        Assert.NotNull(result.Terminal);
        Assert.Equal(ProgressEventKind.Result, result.Terminal!.Kind);
        Assert.Equal(["map.html"], result.Terminal.Outputs);
        Assert.Equal(4, result.Events.Count);
        Assert.Empty(result.MalformedLines);
    }

    [Fact]
    public async Task Error_terminal_with_nonzero_exit_is_not_success()
    {
        var cli = WriteFakeCli(
        [
            """{"v": 1, "event": "start", "command": "flightmap"}""",
            """{"v": 1, "event": "error", "message": "No .SRT telemetry files found"}""",
        ], exitCode: 1);
        var result = await new DjiEmbedRunner().RunAsync(cli, ["flightmap", "/x"]);

        Assert.Equal(1, result.ExitCode);
        Assert.False(result.Success);
        Assert.Equal(ProgressEventKind.Error, result.Terminal!.Kind);
        Assert.Equal("No .SRT telemetry files found", result.Terminal.Message);
    }

    [Fact]
    public async Task Embed_partial_failure_exit_zero_result_not_ok_is_not_success()
    {
        // The contract's embed nuance: per-file failures exit 0 with
        // result.ok == false. The UI must treat that as "attention needed".
        var cli = WriteFakeCli(
        [
            """{"v": 1, "event": "start", "command": "embed", "total": 1}""",
            """{"v": 1, "event": "result", "ok": false, "outputs": [], "summary": {"errors": ["x.mp4"]}}""",
        ]);
        var result = await new DjiEmbedRunner().RunAsync(cli, ["embed", "/x"]);

        Assert.Equal(0, result.ExitCode);
        Assert.False(result.Success);
        Assert.False(result.Terminal!.Ok);
    }

    [Fact]
    public async Task Garbage_stdout_lines_are_collected_not_fatal()
    {
        var cli = WriteFakeCli(
        [
            HappyStream[0],
            "Traceback (most recent call last):",
            HappyStream[3],
        ]);
        var result = await new DjiEmbedRunner().RunAsync(cli, ["flightmap", "/x"]);

        Assert.True(result.Success);
        Assert.Single(result.MalformedLines);
        Assert.Contains("Traceback", result.MalformedLines[0]);
    }

    [Fact]
    public async Task Missing_terminal_event_is_not_success_even_on_exit_zero()
    {
        // A crash after start (or a kill) can end the stream without result
        // or error; the contract says exactly one terminal event, so its
        // absence means the run cannot be trusted.
        var cli = WriteFakeCli([HappyStream[0], HappyStream[1]]);
        var result = await new DjiEmbedRunner().RunAsync(cli, ["flightmap", "/x"]);

        Assert.Equal(0, result.ExitCode);
        Assert.Null(result.Terminal);
        Assert.False(result.Success);
    }

    [Fact]
    public async Task Stderr_is_captured_for_diagnostics()
    {
        var cli = WriteFakeCli(HappyStream, stderrLine: "some log line");
        var result = await new DjiEmbedRunner().RunAsync(cli, ["flightmap", "/x"]);
        Assert.Contains("some log line", result.StderrText);
    }

    [Fact]
    public async Task Appends_the_progress_flag_so_flows_cannot_forget_it()
    {
        // The fake echoes its own argv on stdout as a malformed line; the
        // runner must have added --progress jsonl after the caller's args.
        string cli;
        if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            cli = Path.Combine(_dir, "argv.cmd");
            File.WriteAllText(cli, "@echo off\r\necho ARGS %*\r\nexit /b 0\r\n");
        }
        else
        {
            cli = Path.Combine(_dir, "argv.sh");
            File.WriteAllText(cli, "#!/bin/sh\necho \"ARGS $@\"\nexit 0\n");
            File.SetUnixFileMode(cli,
                UnixFileMode.UserRead | UnixFileMode.UserWrite | UnixFileMode.UserExecute);
        }
        var result = await new DjiEmbedRunner().RunAsync(cli, ["flightmap", "/x"]);
        var argsLine = Assert.Single(result.MalformedLines);
        Assert.Contains("flightmap", argsLine);
        Assert.Contains("--progress jsonl", argsLine);
    }

    [Fact]
    public async Task Cancellation_kills_the_process()
    {
        var cli = WriteFakeCli([HappyStream[0]], sleepSeconds: 30);
        using var cts = CancellationTokenSource.CreateLinkedTokenSource(
            TestContext.Current.CancellationToken);
        cts.CancelAfter(TimeSpan.FromSeconds(2));
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() =>
            new DjiEmbedRunner().RunAsync(cli, ["flightmap", "/x"], ct: cts.Token));
    }
}
