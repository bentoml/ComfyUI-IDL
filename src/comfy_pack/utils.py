from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Union

if TYPE_CHECKING:
    from pydantic import BaseModel

CPACK_OUTPUT_NODES = {
    "CPackOutputFile",
    "CPackOutputImage",
}

CPACK_PATH_INPUT_NODES = {
    "CPackInputFile",
    "CPackInputImage",
}


def _get_node_value(node: dict) -> Any:
    return next(iter(node["inputs"].values()))


def _set_node_value(node: dict, value: Any) -> None:
    key = next(iter(node["inputs"].keys()))
    if isinstance(value, Path):
        value = value.as_posix()
    node["inputs"][key] = value


def _normalize_to_identifier(s: str) -> str:
    if not s:
        return "_"

    s = re.sub(r"[^a-zA-Z0-9_]", "_", s)

    if s[0].isdigit():
        s = "_" + s

    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    s = s if s else "_"
    return s.lower()


def _get_node_identifier(node, dep_map=None) -> str:
    """
    Get the input name from the node
    """
    title = node["_meta"]["title"]
    if title.isidentifier():
        return title
    nid = node["id"]
    if dep_map and (nid, 0) in dep_map:
        _, input_name = dep_map[(nid, 0)]
        return _normalize_to_identifier(input_name)

    return _normalize_to_identifier(title)


API_WORKFLOW_MESSAGE = """
It seems you are trying to parse an ordinary Workflow json file.
Please save the Workflow with the Save (API Format).
If you don't have this button, you must enable the "Dev mode Options" by clicking the Settings button on the top right (gear icon). Check the setting option "Enable Dev Mode options". After that, the Button Save (API Format) should appear.
"""


def _parse_workflow(workflow: dict) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Parse the workflow template and return the input and output definition
    """
    inputs = {}
    outputs = {}
    dep_map = {}

    if "last_node_id" in workflow:
        raise ValueError(API_WORKFLOW_MESSAGE)

    for id, node in workflow.items():
        for input_name, v in node["inputs"].items():
            if isinstance(v, list) and len(v) == 2:  # is a link
                dep_map[tuple(v)] = node, input_name

    for id, node in workflow.items():
        node["id"] = id
        if node["class_type"].startswith("CPackInput"):
            name = _get_node_identifier(node, dep_map)
            if name in inputs:
                name = f"{name}_{id}"
            inputs[name] = node
        elif node["class_type"].startswith("CPackOutput"):
            name = _get_node_identifier(node)
            if name in inputs:
                name = f"{name}_{id}"
            outputs[name] = node

    return inputs, outputs


def parse_workflow(workflow: dict) -> tuple[dict, dict]:
    """
    Describe the workflow template
    """
    return _parse_workflow(workflow)


def generate_input_model(workflow: dict) -> type[BaseModel]:
    """
    Generates a pydantic model from the input definition.

    Args:
        workflow (dict): The workflow template to generate the model from.

    Returns:
        type[BaseModel]: A pydantic model class representing the input definition.

    Raises:
        ValueError: If an unsupported class type is encountered in the workflow.
    """
    from pydantic import Field, create_model
    from pydantic_core import PydanticUndefined

    inputs, _ = _parse_workflow(workflow)

    input_fields = {}
    for name, node in inputs.items():
        class_type = node["class_type"]
        if class_type in CPACK_PATH_INPUT_NODES:
            field = (Path, Field())
        elif class_type == "CPackInputValue":
            options = node.get("_meta", {}).get("options")
            value = _get_node_value(node)
            if not options:
                field = (type(value), Field(default=value))
            else:
                if values := options.get("values"):  # combo type
                    field = (Literal[tuple(values)], Field(default=value))
                elif any(
                    f in options for f in ("min", "max", "round", "precision", "step")
                ):  # must be number types
                    type_ = float if options.get("round", 1) < 1 else int
                    field = (
                        type_,
                        Field(
                            default=value,
                            ge=options.get("min", PydanticUndefined),
                            le=options.get("max", PydanticUndefined),
                        ),
                    )
                else:
                    field = (type(value), Field(default=value))
        else:
            raise ValueError(f"Unsupported class type: {class_type}")
        input_fields[name] = field
    return create_model("ParsedWorkflowTemplate", **input_fields)


def populate_workflow(
    workflow: dict,
    output_path: Path,
    session_id: str = "",
    **inputs,
) -> dict:
    """
    Fills the input values and output path into the workflow.

    Args:
        workflow (dict): The workflow template to populate.
        output_path (Path): The path where output files will be saved.
        **inputs: Keyword arguments representing input values for the workflow.

    Returns:
        dict: The populated workflow with input values and output paths set.

    Raises:
        ValueError: If a provided input key does not correspond to an input node.
    """
    input_spec, output_spec = _parse_workflow(workflow)
    for k, v in inputs.items():
        node = input_spec[k]
        if not node["class_type"].startswith("CPackInput"):
            raise ValueError(f"Node {k} is not an input node")
        _set_node_value(workflow[node["id"]], v)

    for _, node in output_spec.items():
        node_id = node["id"]
        if node["class_type"] in CPACK_OUTPUT_NODES:
            workflow[node_id]["inputs"]["filename_prefix"] = (
                output_path / f"{session_id}{node_id}_"
            ).as_posix()
    return workflow


def retrieve_workflow_outputs(
    workflow: dict,
    output_path: Path,
    session_id: str = "",
) -> Union[Path, list[Path], dict[str, Path], dict[str, list[Path]]]:
    """
    Gets the output file(s) from the workflow.

    Args:
        workflow (dict): The workflow template to retrieve outputs from.
        output_path (Path): The path where output files are saved.

    Returns:
        Union[Path, list[Path], dict[str, Path], dict[str, list[Path]]]:
            - A single Path if there's only one output file.
            - A list of Paths if there are multiple files for a single output.
            - A dictionary mapping output names to Paths or lists of Paths for multiple outputs.

    Raises:
        ValueError: If the output node is not of the expected type.
    """
    _, outputs = _parse_workflow(workflow)
    if len(outputs) != 1:
        value_map = {}
        for k, node in outputs.items():
            node_id = node["id"]
            path_strs = list(output_path.glob(f"{node_id}_*"))
            if len(path_strs) == 1:
                value_map[k] = path_strs[0]
            else:
                value_map[k] = path_strs
        return value_map

    name, node = next(iter(outputs.items()))
    if node["class_type"] not in CPACK_OUTPUT_NODES:
        raise ValueError(f"Output node {name} is not of type {CPACK_OUTPUT_NODES}")
    node_id = node["id"]

    outs = list(output_path.glob(f"{session_id}{node_id}_*"))
    if len(outs) == 1:
        return outs[0]
    return outs