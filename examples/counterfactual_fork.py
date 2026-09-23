from airtrajectory import (
    BuildingTopology, OpeningEdge, ToyMultizoneEnvironment,
    TransitionAction, ZoneNode, fork_actions,
)


def main():
    topology = BuildingTopology.from_parts(
        [ZoneNode("living", 45), ZoneNode("bedroom", 30)],
        [
            OpeningEdge("w1", "living", "OUTSIDE", "window", 1.2),
            OpeningEdge("door", "living", "bedroom", "door", 1.8),
            OpeningEdge("w2", "bedroom", "OUTSIDE", "window", 1.0),
        ],
    )
    env = ToyMultizoneEnvironment(
        topology,
        {"living": 1400, "bedroom": 1150},
        horizon_steps=30,
    )
    env.reset()
    env.step([TransitionAction("door", 100)])

    branches = fork_actions(
        env,
        {
            "W1 25%": [TransitionAction("w1", 25), TransitionAction("door", 100)],
            "W1 50%": [TransitionAction("w1", 50), TransitionAction("door", 100)],
            "W1 75%": [TransitionAction("w1", 75), TransitionAction("door", 100)],
            "W1 50% + W2 50%": [
                TransitionAction("w1", 50),
                TransitionAction("w2", 50),
                TransitionAction("door", 100),
            ],
        },
        horizon_steps=10,
    )

    print("Counterfactual futures from the same physical state")
    for label, branch in branches.items():
        final = branch.observations[-1]
        print(
            f"{label:18} "
            f"living={final['co2_ppm']['living']:.1f} "
            f"bedroom={final['co2_ppm']['bedroom']:.1f} "
            f"return={branch.return_value:.3f}"
        )


if __name__ == "__main__":
    main()
