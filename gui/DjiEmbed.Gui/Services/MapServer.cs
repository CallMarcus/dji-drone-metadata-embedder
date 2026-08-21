using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Manages one <c>dji-embed serve</c> child per served folder so GUI-made
/// maps open over local HTTP instead of file:// — browsers block the 360°
/// panorama viewer's WebGL image access on file:// pages (#305). The child
/// prints its URL as the first stdout line (<c>--url-only</c>) and stops
/// when its stdin closes (<c>--exit-with-stdin</c>): the held-open pipe is
/// the lifeline, so a server can never outlive this app even if no kill
/// ever runs.
/// </summary>
public sealed class MapServer : IMapServer, IDisposable
{
    private static readonly TimeSpan StartTimeout = TimeSpan.FromSeconds(10);

    // Keeps the log useful without letting it grow forever: at the cap the
    // live file rotates to "<name>.1" (overwriting the previous rotation),
    // so disk usage is bounded at about twice the cap.
    private const long LogCapBytes = 512 * 1024;

    private readonly Dictionary<string, (Process Process, string BaseUrl)> _running =
        new(StringComparer.OrdinalIgnoreCase);

    private readonly string? _logPath;
    private readonly object _logLock = new();
    private StreamWriter? _logWriter;
    private bool _logBroken;

    public MapServer() : this(DefaultLogPath)
    {
    }

    /// <summary>Test seam: an explicit log location, or null to discard
    /// the helpers' output like the pre-#531 behaviour.</summary>
    public MapServer(string? logPath)
    {
        _logPath = logPath;
    }

    /// <summary>Where the helpers' terminal output lands (#531): the one
    /// place a field report can recover per-save timing lines from a GUI
    /// session. Lives beside <see cref="GuiState.DefaultPath"/>.</summary>
    public static string DefaultLogPath => Path.Combine(
        Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
        "DjiEmbed", "helper.log");

    /// <summary>
    /// URL serving <paramref name="htmlPath"/>, starting (or reusing) its
    /// folder's server. Null when no server could be started — the caller
    /// falls back to opening the file directly (the map minus the pano
    /// viewer, never nothing).
    /// </summary>
    public async Task<string?> GetUrlAsync(
        string cliPath, string htmlPath, CancellationToken cancellationToken)
    {
        var dir = Path.GetDirectoryName(Path.GetFullPath(htmlPath));
        if (dir is null)
        {
            return null;
        }
        var page = Path.GetFileName(htmlPath);
        var baseUrl = await LaunchAsync(
            cliPath, dir,
            ["serve", dir, "--page", page, "--no-browser", "--url-only",
             "--exit-with-stdin"],
            cancellationToken);
        return baseUrl is null ? null : baseUrl + page;
    }

    public Task<string?> GetEditorUrlAsync(
        string cliPath, string folder, bool fullResolution,
        CancellationToken cancellationToken)
    {
        var dir = Path.GetFullPath(folder);
        // The key prefix keeps a served map folder and an edited pano
        // folder from colliding in the reuse table — and carries the
        // resolution mode, so toggling it launches a fresh child instead
        // of reusing one serving the other size (#532). The editor's URL
        // is its base URL (the child prints "http://127.0.0.1:PORT/").
        string[] args = fullResolution
            ? ["panoedit", dir, "--max-width", "0", "--no-browser",
               "--url-only", "--exit-with-stdin"]
            : ["panoedit", dir, "--no-browser", "--url-only",
               "--exit-with-stdin"];
        return LaunchAsync(
            cliPath, "panoedit:" + (fullResolution ? "full:" : "") + dir,
            args, cancellationToken);
    }

    /// <summary>One child per <paramref name="key"/>: reuses a live one,
    /// reaps a dead one, else spawns <paramref name="args"/> and reads the
    /// URL contract. Returns the child's base URL (through the trailing
    /// slash), or null when it could not start.</summary>
    private async Task<string?> LaunchAsync(
        string cliPath, string key, string[] args,
        CancellationToken cancellationToken)
    {
        if (_running.TryGetValue(key, out var live))
        {
            if (!live.Process.HasExited)
            {
                return live.BaseUrl;
            }
            live.Process.Dispose();   // dead child: reap the handle too
            _running.Remove(key);
        }

        var psi = new ProcessStartInfo
        {
            FileName = cliPath,
            RedirectStandardInput = true,   // held open: the child's lifeline
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = true,
            StandardOutputEncoding = Encoding.UTF8,
        };
        foreach (var a in args)
        {
            psi.ArgumentList.Add(a);
        }
        var process = new Process { StartInfo = psi };
        try
        {
            process.Start();
        }
        catch (Exception)
        {
            return null;
        }
        // The child logs to stderr for its whole life, and nothing here
        // reads it: an undrained pipe fills within a few KB, after which
        // the child's next write blocks in the kernel. One of those writes
        // sat inside panoedit's save chain, freezing every later save
        // until this app exited and broke the pipe (#490). Drain always;
        // since #531 the drained lines also go to the helper log — that
        // discarded "terminal log" turned out to be exactly the evidence
        // a field report needs (per-save ExifTool timings). Logging is
        // best-effort only: a broken log falls back to discarding, never
        // to an undrained pipe.
        var label = args[0];
        AppendLog(label, "started: " + psi.FileName + " "
            + string.Join(' ', args));
        _ = DrainAsync(process.StandardError, label);
        var url = await ReadUrlLineAsync(process, cancellationToken);
        // Same hazard on stdout: only the URL line is ever read, so any
        // later stdout output would hit the same full-pipe block.
        _ = DrainAsync(process.StandardOutput, label);
        if (url is null)
        {
            TryKill(process);
            process.Dispose();
            return null;
        }
        var baseUrl = url[..(url.LastIndexOf('/') + 1)];
        _running[key] = (process, baseUrl);
        return baseUrl;
    }

    private static async Task<string?> ReadUrlLineAsync(
        Process process, CancellationToken cancellationToken)
    {
        var read = process.StandardOutput.ReadLineAsync();
        if (await Task.WhenAny(
                read, Task.Delay(StartTimeout, cancellationToken)) != read)
        {
            if (cancellationToken.IsCancellationRequested)
            {
                // Canceled must not look like "server failed to start":
                // reap the just-started child, then let the flow unwind.
                TryKill(process);
                process.Dispose();
                throw new OperationCanceledException(cancellationToken);
            }
            return null;
        }
        var line = (await read)?.Trim();
        return line is not null
            && line.StartsWith("http://127.0.0.1:", StringComparison.Ordinal)
            ? line
            : null;
    }

    /// <summary>Reads a child stream to the end, so the child can never
    /// block on a full pipe (#490), appending each line to the helper log
    /// (#531). Runs until the child exits; any error just means the pipe
    /// is already gone.</summary>
    private async Task DrainAsync(StreamReader reader, string label)
    {
        try
        {
            while (await reader.ReadLineAsync() is { } line)
            {
                AppendLog(label, line);
            }
        }
        catch (Exception)
        {
            // Child exited or was killed; nothing left to drain.
        }
    }

    /// <summary>Appends one timestamped line to the helper log, opening
    /// (and rotating) it on first use. Any failure permanently downgrades
    /// to discarding: the log must never be able to reintroduce the
    /// blocked-pipe stall it exists to diagnose (#490, #531).</summary>
    private void AppendLog(string label, string line)
    {
        if (_logPath is null || _logBroken)
        {
            return;
        }
        lock (_logLock)
        {
            try
            {
                if (_logWriter is null
                    || _logWriter.BaseStream.Length > LogCapBytes)
                {
                    _logWriter?.Dispose();
                    _logWriter = null;
                    if (Path.GetDirectoryName(_logPath) is { Length: > 0 } dir)
                    {
                        Directory.CreateDirectory(dir);
                    }
                    var existing = new FileInfo(_logPath);
                    if (existing.Exists && existing.Length > LogCapBytes)
                    {
                        File.Move(_logPath, _logPath + ".1", overwrite: true);
                    }
                    // FileShare.Read so "read the log" support advice works
                    // while the app is running.
                    _logWriter = new StreamWriter(new FileStream(
                        _logPath, FileMode.Append, FileAccess.Write,
                        FileShare.Read))
                    { AutoFlush = true };
                }
                _logWriter.WriteLine(
                    $"{DateTime.Now:yyyy-MM-dd HH:mm:ss} [{label}] {line}");
            }
            catch (Exception)
            {
                _logBroken = true;
                _logWriter?.Dispose();
                _logWriter = null;
            }
        }
    }

    private static void TryKill(Process process)
    {
        try
        {
            process.Kill(entireProcessTree: true);
        }
        catch (Exception)
        {
            // Already gone.
        }
    }

    public void Dispose()
    {
        foreach (var (process, _) in _running.Values)
        {
            TryKill(process);
            process.Dispose();
        }
        _running.Clear();
        lock (_logLock)
        {
            _logWriter?.Dispose();
            _logWriter = null;
        }
    }
}
