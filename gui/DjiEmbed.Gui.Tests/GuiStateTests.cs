using System.Text.Json;
using DjiEmbed.Gui.Services;

namespace DjiEmbed.Gui.Tests;

public class GuiStateTests : IDisposable
{
    private readonly string _dir =
        Directory.CreateTempSubdirectory("djiembed-guistate-tests").FullName;

    public void Dispose() => Directory.Delete(_dir, recursive: true);

    private string StatePath => Path.Combine(_dir, "state.json");

    [Fact]
    public void Missing_file_loads_as_the_Empty_singleton()
    {
        Assert.Same(GuiState.Empty, GuiState.Load(StatePath));
    }

    [Fact]
    public void Corrupt_json_loads_as_the_Empty_singleton()
    {
        File.WriteAllText(StatePath, "{ not json at all");
        Assert.Same(GuiState.Empty, GuiState.Load(StatePath));
    }

    [Fact]
    public void Wrongly_typed_json_loads_as_the_Empty_singleton()
    {
        File.WriteAllText(StatePath, """{"recentFolders": 42}""");
        Assert.Same(GuiState.Empty, GuiState.Load(StatePath));
    }

    [Fact]
    public void State_round_trips_through_the_file()
    {
        var state = new GuiState(
            new WindowBounds(10, 20, 1200, 800, Maximized: true),
            ["C:\\Drone\\latest", "D:\\Trips\\alps"]);

        GuiState.Save(state, StatePath);
        var loaded = GuiState.Load(StatePath);

        Assert.Equal(new WindowBounds(10, 20, 1200, 800, true), loaded.Window);
        Assert.Equal(["C:\\Drone\\latest", "D:\\Trips\\alps"],
            loaded.RecentFolders);
    }

    [Fact]
    public void Wire_format_is_camel_case()
    {
        GuiState.Save(new GuiState(
            new WindowBounds(1, 2, 3, 4, false), ["x"]), StatePath);
        using var doc = JsonDocument.Parse(File.ReadAllText(StatePath));
        Assert.True(doc.RootElement.TryGetProperty("window", out var w));
        Assert.Equal(1, w.GetProperty("x").GetInt32());
        Assert.False(w.GetProperty("maximized").GetBoolean());
        Assert.Equal("x",
            doc.RootElement.GetProperty("recentFolders")[0].GetString());
    }

    [Fact]
    public void Unknown_fields_are_ignored_on_load()
    {
        File.WriteAllText(StatePath,
            """{"recentFolders": ["a"], "futureThing": {"nested": 1}}""");
        Assert.Equal(["a"], GuiState.Load(StatePath).RecentFolders);
    }

    [Fact]
    public void Save_leaves_no_temp_file_behind()
    {
        GuiState.Save(GuiState.Empty.WithRecent("a"), StatePath);
        Assert.Equal([StatePath],
            Directory.GetFiles(_dir).Select(Path.GetFullPath));
    }

    [Fact]
    public void Save_creates_the_directory()
    {
        var nested = Path.Combine(_dir, "DjiEmbed", "state.json");
        GuiState.Save(GuiState.Empty.WithRecent("a"), nested);
        Assert.Equal(["a"], GuiState.Load(nested).RecentFolders);
    }

    [Fact]
    public void Save_failure_is_swallowed()
    {
        // The target IS a directory — the final move cannot succeed.
        // (Inside _dir, so the orphaned temp file is cleaned up too.)
        var target = Path.Combine(_dir, "sub");
        Directory.CreateDirectory(target);
        GuiState.Save(GuiState.Empty.WithRecent("a"), target);
    }

    [Fact]
    public void WithRecent_pushes_to_the_front()
    {
        var state = GuiState.Empty.WithRecent("a").WithRecent("b");
        Assert.Equal(["b", "a"], state.RecentFolders);
    }

    [Fact]
    public void WithRecent_dedupes_case_insensitively()
    {
        var state = GuiState.Empty
            .WithRecent("C:\\Drone").WithRecent("b").WithRecent("c:\\drone");
        Assert.Equal(["c:\\drone", "b"], state.RecentFolders);
    }

    [Fact]
    public void WithRecent_caps_at_five()
    {
        var state = GuiState.Empty;
        foreach (var f in new[] { "a", "b", "c", "d", "e", "f" })
        {
            state = state.WithRecent(f);
        }
        Assert.Equal(["f", "e", "d", "c", "b"], state.RecentFolders);
    }

    [Fact]
    public void Load_caps_an_oversized_stored_list()
    {
        File.WriteAllText(StatePath,
            """{"recentFolders": ["a","b","c","d","e","f","g"]}""");
        Assert.Equal(5, GuiState.Load(StatePath).RecentFolders.Count);
    }

    public static readonly TheoryData<WindowBounds, bool> RestoreCases = new()
    {
        // Fully inside the single 1920×1080 screen.
        { new WindowBounds(100, 100, 800, 600, false), true },
        // Overlapping the right edge still counts.
        { new WindowBounds(1800, 100, 800, 600, false), true },
        // Entirely off to the right (undocked-monitor case).
        { new WindowBounds(2000, 100, 800, 600, false), false },
        // Entirely above.
        { new WindowBounds(100, -700, 800, 600, false), false },
        // Degenerate size never restores.
        { new WindowBounds(100, 100, 0, 600, false), false },
    };

    [Theory]
    [MemberData(nameof(RestoreCases))]
    public void RestorableOn_requires_intersection_with_a_screen(
        WindowBounds bounds, bool expected)
    {
        Assert.Equal(expected,
            GuiState.RestorableOn(bounds, [(0, 0, 1920, 1080)]));
    }

    [Fact]
    public void RestorableOn_second_screen_counts()
    {
        Assert.True(GuiState.RestorableOn(
            new WindowBounds(2000, 100, 800, 600, false),
            [(0, 0, 1920, 1080), (1920, 0, 1920, 1080)]));
    }

    [Fact]
    public void RestorableOn_no_screens_means_restorable()
    {
        // Headless platforms report no screens; restoring is harmless there.
        Assert.True(GuiState.RestorableOn(
            new WindowBounds(100, 100, 800, 600, false), []));
    }

    [Fact]
    public void Default_path_is_the_DjiEmbed_config_file()
    {
        Assert.EndsWith(Path.Combine("DjiEmbed", "state.json"),
            GuiState.DefaultPath);
    }
}
