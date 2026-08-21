using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class MapServerTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-mapserver-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string MapFile(string name = "photomap.html")
    {
        var folder = Path.Combine(_dir, "maps");
        Directory.CreateDirectory(folder);
        var path = Path.Combine(folder, name);
        File.WriteAllText(path, "<p>map</p>");
        return path;
    }

    // Every test passes an explicit log path so nothing ever writes to the
    // real per-user location (#531).
    private string LogPath() => Path.Combine(_dir, "logs", "helper.log");

    private static async Task<string> WaitForLogAsync(
        string logPath, string needle)
    {
        var deadline = DateTime.UtcNow.AddSeconds(20);
        while (DateTime.UtcNow < deadline)
        {
            if (File.Exists(logPath))
            {
                // FileShare-friendly read: the writer holds the file open.
                using var stream = new FileStream(logPath, FileMode.Open,
                    FileAccess.Read, FileShare.ReadWrite);
                using var reader = new StreamReader(stream);
                var text = await reader.ReadToEndAsync();
                if (text.Contains(needle))
                {
                    return text;
                }
            }
            await Task.Delay(100, TestContext.Current.CancellationToken);
        }
        return File.Exists(logPath) ? File.ReadAllText(logPath) : "";
    }

    [Fact]
    public async Task Returns_the_first_stdout_line_as_the_url()
    {
        using var server = new MapServer(LogPath());
        // The fake stays alive after printing, like a real serve child.
        var cli = FakeCli.WriteEventStream(_dir,
            ["http://127.0.0.1:54321/photomap.html"], sleepSeconds: 30);
        var url = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.Equal("http://127.0.0.1:54321/photomap.html", url);
    }

    [Fact]
    public async Task Reuses_the_folder_server_for_a_second_page()
    {
        using var server = new MapServer(LogPath());
        var cli = FakeCli.WriteEventStream(_dir,
            ["http://127.0.0.1:54321/photomap.html"], sleepSeconds: 30);
        await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        // Same folder, other map: no second child — the URL is composed
        // from the running server's base address.
        var url = await server.GetUrlAsync(
            cli, MapFile("flightmap.html"), CancellationToken.None);
        Assert.Equal("http://127.0.0.1:54321/flightmap.html", url);
    }

    [Fact]
    public async Task Non_url_output_yields_null_for_the_file_fallback()
    {
        using var server = new MapServer(LogPath());
        var cli = FakeCli.WriteEventStream(_dir,
            ["Serving map at http://127.0.0.1:54321/ - press Ctrl+C to stop"],
            sleepSeconds: 30);
        Assert.Null(await server.GetUrlAsync(
            cli, MapFile(), CancellationToken.None));
    }

    [Fact]
    public async Task Dead_server_is_replaced_on_the_next_open()
    {
        using var server = new MapServer(LogPath());
        // Exits right after printing — a crashed/killed server.
        var cli = FakeCli.WriteEventStream(_dir,
            ["http://127.0.0.1:54321/photomap.html"]);
        var first = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.NotNull(first);
        await Task.Delay(500, TestContext.Current.CancellationToken);
        var second = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.NotNull(second);
    }

    // #490: MapServer redirects the child's stderr (and stdout) but only
    // ever reads the URL line. A child that logs enough to fill the
    // undrained pipe blocks in the kernel mid-write — in the field that
    // froze panoedit's save chain until the app was closed. Both streams
    // must be drained for the child's whole life.

    private async Task AssertChildIsNotBlockedAsync(bool floodStderr)
    {
        using var server = new MapServer(LogPath());
        var done = Path.Combine(_dir, $"flood-done-{floodStderr}");
        var cli = FakeCli.WritePipeFlood(_dir,
            "http://127.0.0.1:54321/photomap.html", done, floodStderr);
        var url = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.NotNull(url);
        var deadline = DateTime.UtcNow.AddSeconds(20);
        while (!File.Exists(done) && DateTime.UtcNow < deadline)
        {
            await Task.Delay(100, TestContext.Current.CancellationToken);
        }
        Assert.True(File.Exists(done),
            "child blocked on an undrained pipe — the #490 save deadlock");
    }

    [Fact]
    public Task A_stderr_flooding_child_is_never_blocked() =>
        AssertChildIsNotBlockedAsync(floodStderr: true);

    [Fact]
    public Task A_stdout_flooding_child_is_never_blocked() =>
        AssertChildIsNotBlockedAsync(floodStderr: false);

    [Fact]
    public async Task Unstartable_cli_yields_null()
    {
        using var server = new MapServer(LogPath());
        var cli = Path.Combine(_dir, "does-not-exist");
        Assert.Null(await server.GetUrlAsync(
            cli, MapFile(), CancellationToken.None));
    }

    // #531: the drained helper output used to be discarded — which threw
    // away exactly the per-save timing lines a field report needs. It now
    // lands in a timestamped helper log.

    [Fact]
    public async Task Helper_stderr_lines_land_in_the_log()
    {
        using var server = new MapServer(LogPath());
        var cli = FakeCli.WriteEventStream(_dir,
            ["http://127.0.0.1:54321/photomap.html"],
            stderrLine: "ExifTool wrote pano.jpg in 0.7s");
        var url = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.NotNull(url);
        var text = await WaitForLogAsync(
            LogPath(), "ExifTool wrote pano.jpg in 0.7s");
        Assert.Contains("ExifTool wrote pano.jpg in 0.7s", text);
        // The label says which helper spoke, the header which CLI ran.
        Assert.Contains("[serve]", text);
        Assert.Contains("started: " + cli, text);
    }

    [Fact]
    public async Task Oversized_log_rotates_and_keeps_one_predecessor()
    {
        Directory.CreateDirectory(Path.GetDirectoryName(LogPath())!);
        File.WriteAllText(LogPath(),
            "old-session-line\n" + new string('x', 600 * 1024));
        using var server = new MapServer(LogPath());
        var cli = FakeCli.WriteEventStream(_dir,
            ["http://127.0.0.1:54321/photomap.html"],
            stderrLine: "fresh-session-line");
        await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        var text = await WaitForLogAsync(LogPath(), "fresh-session-line");
        Assert.Contains("fresh-session-line", text);
        Assert.DoesNotContain("old-session-line", text);
        Assert.Contains("old-session-line",
            File.ReadAllText(LogPath() + ".1"));
    }

    [Fact]
    public async Task Unwritable_log_never_blocks_serving()
    {
        // The log directory path is occupied by a FILE, so the log can
        // never be created — serving (and draining) must not care.
        File.WriteAllText(Path.Combine(_dir, "logs"), "in the way");
        using var server = new MapServer(LogPath());
        var done = Path.Combine(_dir, "flood-done-unwritable");
        var cli = FakeCli.WritePipeFlood(_dir,
            "http://127.0.0.1:54321/photomap.html", done, toStderr: true);
        var url = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.NotNull(url);
        var deadline = DateTime.UtcNow.AddSeconds(20);
        while (!File.Exists(done) && DateTime.UtcNow < deadline)
        {
            await Task.Delay(100, TestContext.Current.CancellationToken);
        }
        Assert.True(File.Exists(done),
            "child blocked even though logging was meant to degrade");
    }

    [Fact]
    public async Task Null_log_path_discards_like_before()
    {
        using var server = new MapServer(logPath: null);
        var cli = FakeCli.WriteEventStream(_dir,
            ["http://127.0.0.1:54321/photomap.html"],
            stderrLine: "should-go-nowhere");
        Assert.NotNull(await server.GetUrlAsync(
            cli, MapFile(), CancellationToken.None));
        await Task.Delay(500, TestContext.Current.CancellationToken);
        Assert.False(File.Exists(LogPath()));
    }
}
