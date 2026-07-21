using DjiEmbed.Gui.Views;

namespace DjiEmbed.Gui.Tests;

// M4a: ResolveDrop is FolderPicking's pure drop-payload resolution — no
// Avalonia types involved, so it is exercised directly against real temp
// files/dirs rather than through the headless view harness.
public class FolderPickingTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-folderpicking-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string Touch(string name)
    {
        var path = Path.Combine(_dir, name);
        File.WriteAllText(path, "");
        return path;
    }

    private string MakeDir(string name)
    {
        var path = Path.Combine(_dir, name);
        Directory.CreateDirectory(path);
        return path;
    }

    [Theory]
    [InlineData("clip.SRT", false, "file")]   // telemetry file accepted
    [InlineData("movie.mkv", false, "none")]  // wrong extension ignored
    [InlineData("clip.srt", true, "folder")]  // folder in payload wins
    public void Drop_resolution_prefers_folders_then_telemetry_files(
        string fileName, bool includeDir, string expected)
    {
        var file = Touch(fileName);
        var paths = new List<string> { file };
        string? dir = null;
        if (includeDir)
        {
            dir = MakeDir("footage");
            paths.Add(dir);   // file first, dir second — order must not
                               // matter for folder priority
        }

        FolderPicking.ResolveDrop(paths, out var folder, out var resolvedFile);

        switch (expected)
        {
            case "folder":
                Assert.Equal(dir, folder);
                break;
            case "file":
                Assert.Null(folder);
                Assert.Equal(file, resolvedFile);
                break;
            case "none":
                Assert.Null(folder);
                Assert.Null(resolvedFile);
                break;
        }
    }

    [Theory]
    [InlineData("clip.mp4")]
    [InlineData("clip.MOV")]
    public void Drop_resolution_accepts_video_extensions_case_insensitively(
        string fileName)
    {
        var file = Touch(fileName);

        FolderPicking.ResolveDrop([file], out var folder, out var resolvedFile);

        Assert.Null(folder);
        Assert.Equal(file, resolvedFile);
    }
}
