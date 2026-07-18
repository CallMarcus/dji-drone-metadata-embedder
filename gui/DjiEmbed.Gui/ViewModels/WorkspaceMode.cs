using System.Collections.Generic;
using System.Linq;

namespace DjiEmbed.Gui.ViewModels;

public enum WorkspaceModeKind
{
    FlightMap,
    PhotoMap,
    Embed,
    Setup,
}

/// <summary>
/// One entry in the workspace mode strip (GUI 2.0 spec). M1 ships four;
/// Convert and Verify join in M4.
/// </summary>
public sealed record WorkspaceMode(
    WorkspaceModeKind Kind,
    string Title,
    string Verb,
    bool NeedsFolder,
    string FailureMessage)
{
    public static readonly IReadOnlyList<WorkspaceMode> All =
    [
        new(WorkspaceModeKind.FlightMap, "Flight map", "Generate flight map",
            NeedsFolder: true,
            "Something went wrong while mapping your flights."),
        new(WorkspaceModeKind.PhotoMap, "Photo map", "Generate photo map",
            NeedsFolder: true,
            "Something went wrong while mapping your photos."),
        new(WorkspaceModeKind.Embed, "Embed telemetry", "Embed telemetry",
            NeedsFolder: true,
            "Something went wrong while embedding the flight data."),
        new(WorkspaceModeKind.Setup, "Setup", "Check my setup",
            NeedsFolder: false,
            "The setup check could not be completed."),
    ];

    public static WorkspaceMode Of(WorkspaceModeKind kind) =>
        All.First(m => m.Kind == kind);
}
