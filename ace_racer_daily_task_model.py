#!/usr/bin/env python3
"""《王牌竞速》日常任务系统轻量验证模型。

参数为反策划示例，并非官方当前版本数值。模型按“活跃度/增量分钟”排序，
依次选择任务，计算轻度、普通和全勤三种目标路径。

用法：
  python ace_racer_daily_task_model.py --output-dir results
  python ace_racer_daily_task_model.py --write-default config.json
  python ace_racer_daily_task_model.py --config config.json --output-dir results
  python ace_racer_daily_task_model.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List


DEFAULT_CONFIG: Dict[str, Any] = {
    "note": "示例参数，仅用于作品集建模；增量耗时已考虑任务并行完成。",
    "tasks": [
        {"id": "T01", "category": "登录", "name": "登录游戏", "minutes": 0.5, "activity": 10, "reward_value": 20, "daily_limit": 1},
        {"id": "T02", "category": "登录", "name": "领取免费奖励", "minutes": 0.5, "activity": 5, "reward_value": 15, "daily_limit": 1},
        {"id": "T03", "category": "社交", "name": "完成俱乐部签到", "minutes": 1.0, "activity": 10, "reward_value": 30, "daily_limit": 1},
        {"id": "T04", "category": "浏览", "name": "查看当日活动", "minutes": 1.0, "activity": 5, "reward_value": 15, "daily_limit": 1},
        {"id": "T05", "category": "养成", "name": "完成一次车辆或芯片强化", "minutes": 2.0, "activity": 10, "reward_value": 25, "daily_limit": 1},
        {"id": "T06", "category": "比赛", "name": "完成1场比赛", "minutes": 4.0, "activity": 15, "reward_value": 40, "daily_limit": 1},
        {"id": "T07", "category": "比赛", "name": "完成3场比赛", "minutes": 12.0, "activity": 25, "reward_value": 80, "daily_limit": 1},
        {"id": "T08", "category": "表现", "name": "达成一次指定比赛表现", "minutes": 6.0, "activity": 10, "reward_value": 35, "daily_limit": 1},
        {"id": "T09", "category": "排位", "name": "完成1场排位赛", "minutes": 7.0, "activity": 15, "reward_value": 50, "daily_limit": 1},
        {"id": "T10", "category": "挑战", "name": "完成2场挑战赛", "minutes": 8.0, "activity": 10, "reward_value": 45, "daily_limit": 1},
        {"id": "T11", "category": "社交", "name": "与好友组队完成1场", "minutes": 7.0, "activity": 15, "reward_value": 55, "daily_limit": 1},
        {"id": "T12", "category": "比赛", "name": "累计完成5场比赛", "minutes": 16.0, "activity": 20, "reward_value": 70, "daily_limit": 1},
    ],
    "milestones": [
        {"name": "轻度", "target_activity": 30},
        {"name": "普通", "target_activity": 80},
        {"name": "全勤", "target_activity": 100},
    ],
    "reward_nodes": [
        {"activity": 20, "reward_value": 30},
        {"activity": 40, "reward_value": 40},
        {"activity": 60, "reward_value": 60},
        {"activity": 80, "reward_value": 100},
        {"activity": 100, "reward_value": 170},
    ],
}


def validate(config: Dict[str, Any]) -> None:
    if not config.get("tasks"):
        raise ValueError("任务列表不能为空")
    ids = [task["id"] for task in config["tasks"]]
    if len(ids) != len(set(ids)):
        raise ValueError("任务ID必须唯一")
    for task in config["tasks"]:
        if float(task["minutes"]) < 0:
            raise ValueError(f"任务 {task['id']} 的耗时不能为负")
        if int(task["activity"]) < 0 or int(task["daily_limit"]) < 1:
            raise ValueError(f"任务 {task['id']} 的活跃度或次数无效")


def activity_efficiency(task: Dict[str, Any]) -> float:
    minutes = float(task["minutes"])
    activity = float(task["activity"])
    if minutes == 0:
        return math.inf if activity > 0 else 0.0
    return activity / minutes


def reward_efficiency(task: Dict[str, Any]) -> float:
    minutes = float(task["minutes"])
    reward = float(task["reward_value"])
    if minutes == 0:
        return math.inf if reward > 0 else 0.0
    return reward / minutes


def reward_coverage(activity: float, reward_nodes: List[Dict[str, Any]]) -> tuple[float, float]:
    earned = sum(float(node["reward_value"]) for node in reward_nodes if activity >= float(node["activity"]))
    total = sum(float(node["reward_value"]) for node in reward_nodes)
    return earned, earned / total if total else 0.0


def choose_path(config: Dict[str, Any], target_activity: float) -> Dict[str, Any]:
    expanded: List[Dict[str, Any]] = []
    for task in config["tasks"]:
        for occurrence in range(1, int(task["daily_limit"]) + 1):
            item = deepcopy(task)
            item["occurrence"] = occurrence
            expanded.append(item)
    expanded.sort(key=lambda item: (-activity_efficiency(item), -reward_efficiency(item), item["minutes"], item["id"]))

    selected: List[Dict[str, Any]] = []
    total_activity = total_minutes = total_task_rewards = 0.0
    for task in expanded:
        if total_activity >= target_activity:
            break
        selected.append(task)
        total_activity += float(task["activity"])
        total_minutes += float(task["minutes"])
        total_task_rewards += float(task["reward_value"])

    if total_activity < target_activity:
        raise ValueError(f"目标活跃度 {target_activity:g} 不可达；最大可获得 {total_activity:g}")
    node_rewards, coverage = reward_coverage(total_activity, config["reward_nodes"])
    return {
        "target_activity": target_activity,
        "total_activity": total_activity,
        "total_minutes": total_minutes,
        "task_reward_value": total_task_rewards,
        "node_reward_value": node_rewards,
        "reward_coverage": coverage,
        "selected_tasks": selected,
    }


def run_model(config: Dict[str, Any]) -> Dict[str, Any]:
    validate(config)
    total_available = sum(float(task["activity"]) * int(task["daily_limit"]) for task in config["tasks"])
    paths = []
    for milestone in config["milestones"]:
        path = choose_path(config, float(milestone["target_activity"]))
        path["name"] = milestone["name"]
        paths.append(path)
    return {"total_available_activity": total_available, "paths": paths}


def write_outputs(config: Dict[str, Any], result: Dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for path in result["paths"]:
        task_names = "、".join(task["name"] for task in path["selected_tasks"])
        rows.append({
            "path": path["name"],
            "target_activity": path["target_activity"],
            "actual_activity": path["total_activity"],
            "minutes": path["total_minutes"],
            "task_count": len(path["selected_tasks"]),
            "node_reward_value": path["node_reward_value"],
            "reward_coverage": round(path["reward_coverage"], 6),
            "tasks": task_names,
        })
    with (output_dir / "path_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "model_result.json").open("w", encoding="utf-8") as handle:
        json.dump({"config": config, "result": result}, handle, ensure_ascii=False, indent=2)
    print(json.dumps(rows, ensure_ascii=False, indent=2))


def self_test() -> None:
    result = run_model(deepcopy(DEFAULT_CONFIG))
    assert [path["total_minutes"] for path in result["paths"]] == [3.0, 23.0, 35.0]
    assert result["paths"][1]["total_activity"] == 85
    assert result["paths"][2]["reward_coverage"] == 1.0

    zero = deepcopy(DEFAULT_CONFIG)
    zero["tasks"][0]["minutes"] = 0
    assert math.isinf(activity_efficiency(zero["tasks"][0]))

    limited = deepcopy(DEFAULT_CONFIG)
    limited["tasks"] = [limited["tasks"][0]]
    limited["milestones"] = [{"name": "不可达", "target_activity": 30}]
    try:
        run_model(limited)
    except ValueError as error:
        assert "不可达" in str(error)
    else:
        raise AssertionError("不可达节点应抛出错误")

    repeated = deepcopy(DEFAULT_CONFIG)
    repeated["tasks"][0]["daily_limit"] = 2
    path = choose_path(repeated, 15)
    assert len([task for task in path["selected_tasks"] if task["id"] == "T01"]) == 2
    print("全部自检通过：路径耗时、零耗时、不可达节点和次数限制均符合预期。")


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="王牌竞速日常任务活跃度路径模型")
    p.add_argument("--config", type=Path, help="自定义JSON配置")
    p.add_argument("--output-dir", type=Path, default=Path("model_output"), help="结果目录")
    p.add_argument("--write-default", type=Path, help="写出默认配置")
    p.add_argument("--self-test", action="store_true", help="运行自检")
    return p


def main() -> None:
    args = parser().parse_args()
    if args.write_default:
        args.write_default.parent.mkdir(parents=True, exist_ok=True)
        args.write_default.write_text(json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写出：{args.write_default}")
        return
    if args.self_test:
        self_test()
        return
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else deepcopy(DEFAULT_CONFIG)
    result = run_model(config)
    write_outputs(config, result, args.output_dir)


if __name__ == "__main__":
    main()
