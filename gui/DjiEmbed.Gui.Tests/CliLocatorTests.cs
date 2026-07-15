using System.Runtime.InteropServices;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class CliLocatorTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-locator-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private static string ExeName =>
        RuntimeInformation.IsOSPlatform(OSPlatform.Windows)
            ? "dji-embed.exe" : "dji-embed";

    private string Touch(params string[] parts)
    {
        var path = Path.Combine([_dir, .. parts]);
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);
        File.WriteAllText(path, "");
        return path;
    }

    [Fact]
    public void Env_override_wins_when_it_exists()
    {
        var custom = Touch("custom", "my-cli");
        var beside = Touch("app", ExeName);
        var found = CliLocator.Find(custom, Path.Combine(_dir, "app"), null);
        Assert.Equal(custom, found);
        _ = beside;
    }

    [Fact]
    public void Nonexistent_env_override_is_ignored()
    {
        var beside = Touch("app", ExeName);
        var found = CliLocator.Find(
            Path.Combine(_dir, "missing"), Path.Combine(_dir, "app"), null);
        Assert.Equal(beside, found);
    }

    [Fact]
    public void Finds_cli_beside_the_gui_executable()
    {
        var beside = Touch("app", ExeName);
        Assert.Equal(beside, CliLocator.Find(null, Path.Combine(_dir, "app"), null));
    }

    [Fact]
    public void Finds_cli_in_cli_subdirectory_of_the_app()
    {
        // Installer layout option: keep the bundled CLI (one-dir PyInstaller)
        // in its own subfolder next to the GUI.
        var nested = Touch("app", "cli", ExeName);
        Assert.Equal(nested, CliLocator.Find(null, Path.Combine(_dir, "app"), null));
    }

    [Fact]
    public void Falls_back_to_path_directories()
    {
        var onPath = Touch("bin", ExeName);
        var found = CliLocator.Find(null, Path.Combine(_dir, "app"),
            string.Join(Path.PathSeparator, ["/nonexistent", Path.Combine(_dir, "bin")]));
        Assert.Equal(onPath, found);
    }

    [Fact]
    public void Returns_null_when_nothing_is_found()
    {
        Assert.Null(CliLocator.Find(null, Path.Combine(_dir, "app"), null));
    }
}
