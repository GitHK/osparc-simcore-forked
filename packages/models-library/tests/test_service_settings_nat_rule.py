from itertools import combinations
from typing import Any

import pytest
from _pytest.mark.structures import ParameterSet
from models_library.osparc_variable_identifier import (
    OsparcVariableIdentifier,
    UnresolvedOsparcVariableIdentifierError,
    replace_osparc_variable_identifier,
)
from models_library.service_settings_nat_rule import NATRule
from pydantic import parse_obj_as

SUPPORTED_TEMPLATES: set[str] = {
    "$OSPARC_VARIABLE_%s",
    "${OSPARC_VARIABLE_%s}",
    "${OSPARC_VARIABLE_%s:-%s}",
}


def _format(template: str, *, name: str, default: str) -> dict[str, str]:
    try:
        return {"identifier": template % (name, default)}
    except TypeError:
        return {"identifier": template % (name)}


SERIALIZED_NAT_RULES: list[ParameterSet] = [
    pytest.param(
        {
            "hostname": _format(template, name="hostname", default=""),
            "tcp_ports": [
                _format(template, name="p1", default="12"),
                {
                    "lower": _format(template, name="port_low", default="10"),
                    "upper": _format(template, name="port_high", default="11"),
                },
                8000,
            ],
            "dns_resolver": {
                "address": _format(template, name="dns_address", default="some"),
                "port": _format(template, name="dns_port", default="11111"),
            },
        },
        id=template,
    )
    for template in SUPPORTED_TEMPLATES
]


def _all_combinations_from_list(
    elements: list[Any],
) -> list[tuple[Any, ...]]:
    result: list[tuple[Any, ...]] = []
    for group_size in range(1, len(elements) + 1):
        for combination in combinations(elements, group_size):
            result.append(combination)  # noqa: PERF402
    return result


def _all_combinations_from_dict(data: dict[Any, Any]) -> list[dict[Any, Any]]:
    return [dict(c) for c in _all_combinations_from_list(list(data.items()))]


@pytest.mark.parametrize("nat_rule_dict", SERIALIZED_NAT_RULES)
@pytest.mark.parametrize(
    "osparc_variables",
    _all_combinations_from_dict(
        {
            "OSPARC_VARIABLE_hostname": "a-host-name",
            "OSPARC_VARIABLE_p1": 12,
            "OSPARC_VARIABLE_port_low": 10,
            "OSPARC_VARIABLE_port_high": 12,
            "OSPARC_VARIABLE_dns_address": "dms.local",
            "OSPARC_VARIABLE_dns_port": 44,
        }
    ),
)
def test_nat_rule_with_osparc_variable_identifier(
    nat_rule_dict: dict[str, Any], osparc_variables: dict[str, Any]
):
    nat_rule = parse_obj_as(NATRule, nat_rule_dict)

    with pytest.raises(UnresolvedOsparcVariableIdentifierError):
        list(nat_rule.iter_tcp_ports())

    # NOTE: values are mostly replaced in place unless it's used as first level
    replace_osparc_variable_identifier(nat_rule, osparc_variables)

    nat_rule_str = nat_rule.json()
    for osparc_variable_name in osparc_variables:
        assert osparc_variable_name not in nat_rule_str

    # when all env vars are converted now it works
    if len(osparc_variables) == 6:
        assert list(nat_rule.iter_tcp_ports())


@pytest.mark.parametrize(
    "replace_with_value",
    [
        "a_string",
        1,
        True,
        {"a_set"},
        {"a": "dict"},
        ("a", "tuple"),
    ],
)
def test_replace_an_instance_of_osparcvariable_identifier(replace_with_value: Any):
    a_var = parse_obj_as(
        OsparcVariableIdentifier, {"identifier": "$OSPARC_VARIABLE_some_var"}
    )
    assert isinstance(a_var, OsparcVariableIdentifier)

    replaced_var = replace_osparc_variable_identifier(
        a_var, {"OSPARC_VARIABLE_some_var": replace_with_value}
    )
    # NOTE: after replacement the original reference still points
    assert isinstance(a_var, OsparcVariableIdentifier)
    assert replaced_var == replace_with_value
