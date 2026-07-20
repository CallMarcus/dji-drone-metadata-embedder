using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class FolderInspectorTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-inspector-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private void Touch(params string[] parts)
    {
        var path = Path.Combine([_dir, .. parts]);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, "");
    }

    private void Stamp(DateTime utc, params string[] parts) =>
        File.SetLastWriteTimeUtc(Path.Combine([_dir, .. parts]), utc);

    [Fact]
    public void Detects_flight_logs_only()
    {
        Touch("DJI_0001.SRT");
        var c = FolderInspector.Inspect(_dir);
        Assert.True(c.HasFlightLogs);
        Assert.False(c.HasPhotos);
    }

    [Fact]
    public void Detects_photos_only_case_insensitive_and_nested()
    {
        Touch("sub", "IMG_1.JPG");
        Touch("sub", "deeper", "raw.dng");
        var c = FolderInspector.Inspect(_dir);
        Assert.False(c.HasFlightLogs);
        Assert.True(c.HasPhotos);
    }

    [Fact]
    public void Detects_mixed_content()
    {
        Touch("DJI_0001.srt");
        Touch("photos", "a.jpeg");
        var c = FolderInspector.Inspect(_dir);
        Assert.True(c.HasFlightLogs);
        Assert.True(c.HasPhotos);
    }

    [Fact]
    public void Empty_or_unrelated_folder_detects_nothing()
    {
        Touch("notes.txt");
        var c = FolderInspector.Inspect(_dir);
        Assert.False(c.HasFlightLogs);
        Assert.False(c.HasPhotos);
        Assert.False(c.HasVideos);
    }

    [Fact]
    public void Detects_videos_for_the_embed_flow()
    {
        Touch("clips", "DJI_0001.MP4");
        Touch("clips", "extra.mov");
        var c = FolderInspector.Inspect(_dir);
        Assert.True(c.HasVideos);
        Assert.False(c.HasPhotos);
    }

    [Fact]
    public void Records_the_newest_flight_log_time_across_subfolders()
    {
        var older = new DateTime(2026, 1, 1, 0, 0, 0, DateTimeKind.Utc);
        var newer = new DateTime(2026, 6, 1, 0, 0, 0, DateTimeKind.Utc);
        Touch("DJI_0001.SRT");
        Touch("sub", "DJI_0002.SRT");
        Stamp(older, "DJI_0001.SRT");
        Stamp(newer, "sub", "DJI_0002.SRT");

        var c = FolderInspector.Inspect(_dir);

        Assert.Equal(newer, c.NewestFlightLogUtc);
    }

    [Fact]
    public void Flight_log_and_photo_times_are_tracked_separately()
    {
        var srtTime = new DateTime(2026, 2, 2, 0, 0, 0, DateTimeKind.Utc);
        var photoTime = new DateTime(2026, 5, 5, 0, 0, 0, DateTimeKind.Utc);
        Touch("DJI_0001.SRT");
        Touch("IMG_1.JPG");
        Stamp(srtTime, "DJI_0001.SRT");
        Stamp(photoTime, "IMG_1.JPG");

        var c = FolderInspector.Inspect(_dir);

        Assert.Equal(srtTime, c.NewestFlightLogUtc);
        Assert.Equal(photoTime, c.NewestPhotoUtc);
    }

    [Fact]
    public void A_kind_that_is_absent_has_no_timestamp()
    {
        Touch("IMG_1.JPG");

        var c = FolderInspector.Inspect(_dir);

        Assert.Null(c.NewestFlightLogUtc);
        Assert.NotNull(c.NewestPhotoUtc);
    }
}
