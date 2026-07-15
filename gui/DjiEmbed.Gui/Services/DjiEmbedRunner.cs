using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Outcome of one CLI run. <see cref="Success"/> is deliberately strict:
/// the contract promises exactly one terminal event (result XOR error), so
/// a clean exit without a result — or a result with ok=false, the embed
/// command's per-file-failure nuance — is not success.
/// </summary>
public sealed record CliRunResult(
    int ExitCode,
    ProgressEvent? Terminal,
    IReadOnlyList<ProgressEvent> Events,
    IReadOnlyList<string> MalformedLines,
    string StderrText)
{
    public bool Success =>
        ExitCode == 0 && Terminal is { Kind: ProgressEventKind.Result, Ok: true };
}

/// <summary>
/// Spawns the dji-embed CLI with <c>--progress jsonl</c> appended and
/// surfaces the event stream. This is the GUI's only bridge to the engine:
/// no Python interop, just a child process and stdout (design spec
/// docs/superpowers/specs/2026-07-14-desktop-gui-design.md).
/// </summary>
public sealed class DjiEmbedRunner
{
    public async Task<CliRunResult> RunAsync(
        string cliPath,
        IReadOnlyList<string> args,
        IProgress<ProgressEvent>? progress = null,
        CancellationToken ct = default)
    {
        var psi = new ProcessStartInfo
        {
            FileName = cliPath,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            // The contract is ASCII-safe JSON, but stderr logs may carry
            // arbitrary text; never depend on the OEM codepage.
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8,
        };
        foreach (var a in args)
        {
            psi.ArgumentList.Add(a);
        }
        psi.ArgumentList.Add("--progress");
        psi.ArgumentList.Add("jsonl");

        using var process = new Process { StartInfo = psi };
        process.Start();

        using var registration = ct.Register(() =>
        {
            try
            {
                process.Kill(entireProcessTree: true);
            }
            catch (InvalidOperationException)
            {
                // Already exited between the cancel and the kill.
            }
        });

        var events = new List<ProgressEvent>();
        var malformed = new List<string>();
        ProgressEvent? terminal = null;

        var stderrTask = process.StandardError.ReadToEndAsync(ct);
        while (await process.StandardOutput.ReadLineAsync(ct) is { } line)
        {
            if (line.Length == 0)
            {
                continue;
            }
            var parsed = ProgressEvent.Parse(line);
            if (parsed is null)
            {
                malformed.Add(line);
                continue;
            }
            events.Add(parsed);
            if (parsed.Kind is ProgressEventKind.Result or ProgressEventKind.Error)
            {
                terminal = parsed;
            }
            progress?.Report(parsed);
        }

        await process.WaitForExitAsync(ct);
        var stderr = await stderrTask;
        ct.ThrowIfCancellationRequested();

        return new CliRunResult(process.ExitCode, terminal, events, malformed, stderr);
    }
}
