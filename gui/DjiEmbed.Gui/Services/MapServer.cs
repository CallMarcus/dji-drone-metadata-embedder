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

    private readonly Dictionary<string, (Process Process, string BaseUrl)> _running =
        new(StringComparer.OrdinalIgnoreCase);

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
        if (_running.TryGetValue(dir, out var live))
        {
            if (!live.Process.HasExited)
            {
                return live.BaseUrl + page;
            }
            live.Process.Dispose();   // dead child: reap the handle too
            _running.Remove(dir);
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
        string[] args =
            ["serve", dir, "--page", page, "--no-browser", "--url-only",
             "--exit-with-stdin"];
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
        var url = await ReadUrlLineAsync(process, cancellationToken);
        if (url is null)
        {
            TryKill(process);
            process.Dispose();
            return null;
        }
        _running[dir] = (process, url[..(url.LastIndexOf('/') + 1)]);
        return url;
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
    }
}
