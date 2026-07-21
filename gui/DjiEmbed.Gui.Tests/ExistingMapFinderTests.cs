using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class ExistingMapFinderTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-existing-maps-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private static readonly DateTime Old =
        new(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);

    private static readonly DateTime Recent =
        new(2026, 6, 1, 0, 0, 0, DateTimeKind.Utc);

    private string Map(string fileName, DateTime writtenUtc)
    {
        var path = Path.Combine(_dir, fileName);
        File.WriteAllText(path, "<html></html>");
        File.SetLastWriteTimeUtc(path, writtenUtc);
        return path;
    }

    private static FolderContents Contents(
        DateTime? newestFlightLog = null, DateTime? newestPhoto = null) =>
        new(newestFlightLog is not null, newestPhoto is not null, false,
            newestFlightLog is not null, newestPhoto is not null, false,
            newestFlightLog, newestPhoto);

    [Fact]
    public void A_folder_with_no_maps_yields_nothing()
    {
        Assert.Empty(ExistingMapFinder.Find(_dir, Contents()));
    }

    // Only the CLI's default output names count (#328 spec): a map renamed
    // or redirected by "Save map to" is deliberately out of scope, so an
    // arbitrary .html must never surface as an existing map.
    [Fact]
    public void A_non_default_html_name_is_not_an_existing_map()
    {
        Map("myflight.html", Recent);

        Assert.Empty(ExistingMapFinder.Find(_dir, Contents()));
    }

    [Fact]
    public void Finds_the_flight_map_with_its_title_and_path()
    {
        var path = Map("flightmap.html", Recent);

        var map = Assert.Single(ExistingMapFinder.Find(_dir, Contents()));

        Assert.Equal(path, map.Path);
        Assert.Equal("Flight map", map.Title);
        Assert.Equal(Recent, map.WrittenUtc);
        Assert.False(map.Stale);
    }

    [Fact]
    public void Finds_the_photo_map()
    {
        Map("photomap.html", Recent);

        var map = Assert.Single(ExistingMapFinder.Find(_dir, Contents()));

        Assert.Equal("Photo map", map.Title);
    }

    [Fact]
    public void Lists_the_flight_map_before_the_photo_map()
    {
        Map("photomap.html", Recent);
        Map("flightmap.html", Recent);

        var maps = ExistingMapFinder.Find(_dir, Contents());

        Assert.Equal(["Flight map", "Photo map"],
            maps.Select(m => m.Title).ToArray());
    }

    [Fact]
    public void A_map_older_than_its_own_footage_is_stale()
    {
        Map("flightmap.html", Old);

        var map = Assert.Single(
            ExistingMapFinder.Find(_dir, Contents(newestFlightLog: Recent)));

        Assert.True(map.Stale);
    }

    [Fact]
    public void A_map_newer_than_its_footage_is_not_stale()
    {
        Map("flightmap.html", Recent);

        var map = Assert.Single(
            ExistingMapFinder.Find(_dir, Contents(newestFlightLog: Old)));

        Assert.False(map.Stale);
    }

    [Fact]
    public void New_photos_do_not_make_the_flight_map_stale()
    {
        Map("flightmap.html", Old);

        var map = Assert.Single(
            ExistingMapFinder.Find(_dir, Contents(newestPhoto: Recent)));

        Assert.False(map.Stale);
    }

    [Fact]
    public void A_map_with_no_footage_of_its_kind_is_not_stale()
    {
        Map("photomap.html", Old);

        var map = Assert.Single(ExistingMapFinder.Find(_dir, Contents()));

        Assert.False(map.Stale);
    }

    [Fact]
    public void A_photo_map_older_than_its_photos_is_stale()
    {
        Map("photomap.html", Old);

        var map = Assert.Single(
            ExistingMapFinder.Find(_dir, Contents(newestPhoto: Recent)));

        Assert.True(map.Stale);
    }

    [Fact]
    public void Footage_stamped_at_the_maps_own_time_is_not_stale()
    {
        Map("flightmap.html", Recent);

        var map = Assert.Single(
            ExistingMapFinder.Find(_dir, Contents(newestFlightLog: Recent)));

        Assert.False(map.Stale);
    }
}
