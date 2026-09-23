from airtrajectory import (
    BuildingTopology,
    OpeningEdge,
    ToyMultizoneEnvironment,
    TrajectoryStore,
    TransitionAction,
    ZoneNode,
    rollout,
)


def co2_rule_policy(obs):
    co2 = obs["co2_ppm"]["living"]
    target = 75 if co2 > 1000 else 25 if co2 > 800 else 0
    return [TransitionAction("living_window", target)]


def main():
    topology = BuildingTopology.from_parts(
        zones=[ZoneNode("living", 45.0)],
        openings=[
            OpeningEdge(
                "living_window",
                "living",
                "OUTSIDE",
                "window",
                1.2,
            )
        ],
    )

    env = ToyMultizoneEnvironment(
        topology,
        initial_co2={"living": 1400},
        horizon_steps=30,
    )

    trajectory = rollout(
        env,
        co2_rule_policy,
        "single-room-v1",
        "co2-rule-v1",
    )

    TrajectoryStore("artifacts/trajectories.jsonl").append(trajectory)

    print(
        f"trajectory={trajectory.id} "
        f"steps={len(trajectory.steps)} "
        f"return={trajectory.return_value:.3f}"
    )
    print(
        "final_co2="
        f"{trajectory.steps[-1].next_observation['co2_ppm']['living']:.1f} ppm"
    )


if __name__ == "__main__":
    main()
