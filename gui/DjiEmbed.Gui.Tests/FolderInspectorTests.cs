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
}
