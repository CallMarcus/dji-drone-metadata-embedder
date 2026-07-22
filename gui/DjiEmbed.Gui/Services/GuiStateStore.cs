using System.Collections.Generic;
using System.IO;
using System.Linq;

namespace DjiEmbed.Gui.Services;

/// <summary>
/// Owns state.json at runtime: loads once at construction, holds the
/// current state, saves immediately on every change (a crash must not
/// lose the recents). View models see this store, never file paths.
/// </summary>
public sealed class GuiStateStore
{
    private readonly string? _path;

    public GuiState State { get; private set; }

    public GuiStateStore(string? path)
    {
        _path = path;
        State = path is null ? GuiState.Empty : GuiState.Load(path);
    }

    /// <summary>In-memory store for tests and parameterless view-model
    /// construction: never touches disk.</summary>
    public static GuiStateStore Ephemeral() => new(null);

    /// <summary>A run started on this folder — remember it.</summary>
    public void PushRecent(string folder)
    {
        State = State.WithRecent(folder);
        SaveNow();
    }

    /// <summary>Saves the window bounds. Note the save also prunes dead
    /// recent folders as a side effect: <see cref="SaveNow"/> rewrites the
    /// whole state, and window close is as good a moment as a push to
    /// drop them.</summary>
    public void SaveWindow(WindowBounds bounds)
    {
        State = State with { Window = bounds };
        SaveNow();
    }

    /// <summary>Recents that still exist on disk — the only list the UI
    /// shows. The stored file may briefly hold dead paths; they are
    /// dropped on the next save.</summary>
    public IReadOnlyList<string> ExistingRecents() =>
        State.RecentFolders.Where(Directory.Exists).ToList();

    private void SaveNow()
    {
        if (_path is null)
        {
            return;
        }
        State = State with
        {
            RecentFolders = State.RecentFolders
                .Where(Directory.Exists).ToList(),
        };
        GuiState.Save(State, _path);
    }
}
