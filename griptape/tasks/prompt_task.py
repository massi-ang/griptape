from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Callable, Union
from attr import define, field, Factory
from griptape.rules import Ruleset, Rule
from griptape.utils import PromptStack
from griptape.utils import J2
from griptape.tasks import BaseTextInputTask
from griptape.artifacts import TextArtifact, InfoArtifact, ErrorArtifact

if TYPE_CHECKING:
    from griptape.drivers import BasePromptDriver


@define
class PromptTask(BaseTextInputTask):
    prompt_driver: Optional[BasePromptDriver] = field(default=None, kw_only=True)
    rulesets: list[Ruleset] = field(factory=list, kw_only=True)
    rules: list[Rule] = field(factory=list, kw_only=True)
    generate_system_template: Callable[[PromptTask], str] = field(
        default=Factory(
            lambda self: self.default_system_template_generator,
            takes_self=True
        ),
        kw_only=True
    )

    output: Optional[Union[TextArtifact, ErrorArtifact, InfoArtifact]] = field(default=None, init=False)
    
    @rulesets.validator
    def validate_rulesets(self, _, rulesets: list[Ruleset]) -> None:
        if not rulesets:
            return

        if self.rules:
            raise ValueError("can't have both rulesets and rules specified")

    @rules.validator
    def validate_rules(self, _, rules: list[Rule]) -> None:
        if not rules:
            return

        if self.rulesets:
            raise ValueError("can't have both rules and rulesets specified")

    @property
    def all_rulesets(self) -> list[Ruleset]:
        structure_rulesets = []
        if self.structure.rulesets:
            structure_rulesets = self.structure.rulesets
        elif self.structure.rules:
            structure_rulesets = [Ruleset(name="Default Ruleset", rules=self.structure.rules)]

        task_rulesets = []
        if self.rulesets:
            task_rulesets = self.rulesets
        elif self.rules:
            task_rulesets = [Ruleset(name="Additional Ruleset", rules=self.rules)]

        return structure_rulesets + task_rulesets

    @property
    def prompt_stack(self) -> PromptStack:
        stack = PromptStack()
        memory = self.structure.memory

        stack.add_system_input(
            self.generate_system_template(self)
        )

        if memory:
            memory.add_to_prompt_stack(stack)

        stack.add_user_input(self.input.to_text())

        if self.output:
            stack.add_assistant_input(self.output.to_text())

        return stack

    def default_system_template_generator(self, _: PromptTask) -> str:
        return J2("tasks/prompt_task/system.j2").render(
            rulesets=self.all_rulesets
        )

    def run(self) -> TextArtifact:
        self.output = self.active_driver().run(self.prompt_stack)

        return self.output

    def active_driver(self) -> BasePromptDriver:
        if self.prompt_driver is None:
            return self.structure.prompt_driver
        else:
            return self.prompt_driver
