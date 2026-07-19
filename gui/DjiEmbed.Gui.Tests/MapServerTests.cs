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

    [Fact]
    public async Task Returns_the_first_stdout_line_as_the_url()
    {
        using var server = new MapServer();
        // The fake stays alive after printing, like a real serve child.
        var cli = FakeCli.WriteEventStream(_dir,
            ["http://127.0.0.1:54321/photomap.html"], sleepSeconds: 30);
        var url = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.Equal("http://127.0.0.1:54321/photomap.html", url);
    }

    [Fact]
    public async Task Reuses_the_folder_server_for_a_second_page()
    {
        using var server = new MapServer();
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
        using var server = new MapServer();
        var cli = FakeCli.WriteEventStream(_dir,
            ["Serving map at http://127.0.0.1:54321/ - press Ctrl+C to stop"],
            sleepSeconds: 30);
        Assert.Null(await server.GetUrlAsync(
            cli, MapFile(), CancellationToken.None));
    }

    [Fact]
    public async Task Dead_server_is_replaced_on_the_next_open()
    {
        using var server = new MapServer();
        // Exits right after printing — a crashed/killed server.
        var cli = FakeCli.WriteEventStream(_dir,
            ["http://127.0.0.1:54321/photomap.html"]);
        var first = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.NotNull(first);
        await Task.Delay(500, TestContext.Current.CancellationToken);
        var second = await server.GetUrlAsync(cli, MapFile(), CancellationToken.None);
        Assert.NotNull(second);
    }

    [Fact]
    public async Task Unstartable_cli_yields_null()
    {
        using var server = new MapServer();
        var cli = Path.Combine(_dir, "does-not-exist");
        Assert.Null(await server.GetUrlAsync(
            cli, MapFile(), CancellationToken.None));
    }
}
