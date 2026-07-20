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
    public void A_hidden_file_is_still_classified()
    {
        // The walk asks EnumerationOptions to skip nothing by attribute:
        // its default (Hidden | System) would quietly lose media the
        // SearchOption overload used to find.
        // A leading dot is what hidden means on Unix; on Windows it is the
        // attribute bit, which only sticks there.
        Touch(".IMG_1.JPG");
        var path = Path.Combine(_dir, ".IMG_1.JPG");
        if (OperatingSystem.IsWindows())
        {
            File.SetAttributes(path, FileAttributes.Hidden);
        }
        Assert.SkipUnless(File.GetAttributes(path).HasFlag(FileAttributes.Hidden),
            "This filesystem does not carry the Hidden attribute.");

        var c = FolderInspector.Inspect(_dir);

        Assert.True(c.HasPhotos);
    }

    [Fact]
    public void An_unreadable_subfolder_is_skipped_not_thrown()
    {
        // The folder pick runs from an async void handler, so anything the
        // walk throws reaches the dispatcher unobserved.
        Assert.SkipWhen(OperatingSystem.IsWindows(),
            "Permissions are modelled with ACLs on Windows, not file modes.");
        // The Skip above has already ended the test on Windows; the platform
        // analyzer only reads the explicit guard.
        if (!OperatingSystem.IsWindows())
        {
            Touch("IMG_1.JPG");
            Touch("locked", "DJI_0001.SRT");
            var locked = Path.Combine(_dir, "locked");
            File.SetUnixFileMode(locked, UnixFileMode.None);
            try
            {
                Assert.SkipWhen(CanRead(locked),
                    "This user can read the directory anyway (root?).");

                var c = FolderInspector.Inspect(_dir);

                Assert.True(c.HasPhotos);
            }
            finally
            {
                // Dispose deletes the tree recursively; let it back in.
                File.SetUnixFileMode(locked,
                    UnixFileMode.UserRead | UnixFileMode.UserWrite
                    | UnixFileMode.UserExecute);
            }
        }
    }

    private static bool CanRead(string directory)
    {
        try
        {
            foreach (var _ in Directory.EnumerateFiles(directory))
            {
            }
            return true;
        }
        catch (UnauthorizedAccessException)
        {
            return false;
        }
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
