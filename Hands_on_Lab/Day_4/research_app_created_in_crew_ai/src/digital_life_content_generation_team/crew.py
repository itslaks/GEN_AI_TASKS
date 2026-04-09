import os

from crewai import LLM
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import (
	ScrapeWebsiteTool
)





@CrewBase
class DigitalLifeContentGenerationTeamCrew:
    """DigitalLifeContentGenerationTeam crew"""

    
    @agent
    def digital_life_research_specialist(self) -> Agent:
        
        return Agent(
            config=self.agents_config["digital_life_research_specialist"],
            
            
            tools=[				ScrapeWebsiteTool()],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                
                
            ),
            
        )
    
    @agent
    def digital_life_content_writer(self) -> Agent:
        
        return Agent(
            config=self.agents_config["digital_life_content_writer"],
            
            
            tools=[],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                
                
            ),
            
        )
    
    @agent
    def digital_safety_content_editor(self) -> Agent:
        
        return Agent(
            config=self.agents_config["digital_safety_content_editor"],
            
            
            tools=[],
            reasoning=False,
            max_reasoning_attempts=None,
            inject_date=True,
            allow_delegation=False,
            max_iter=25,
            max_rpm=None,
            
            
            max_execution_time=None,
            llm=LLM(
                model="openai/gpt-4o-mini",
                
                
            ),
            
        )
    

    
    @task
    def research_digital_life_topic(self) -> Task:
        return Task(
            config=self.tasks_config["research_digital_life_topic"],
            markdown=False,
            
            
        )
    
    @task
    def write_digital_life_blog_post(self) -> Task:
        return Task(
            config=self.tasks_config["write_digital_life_blog_post"],
            markdown=False,
            
            
        )
    
    @task
    def edit_and_finalize_content(self) -> Task:
        return Task(
            config=self.tasks_config["edit_and_finalize_content"],
            markdown=False,
            
            
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the DigitalLifeContentGenerationTeam crew"""

        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,  # Automatically created by the @task decorator
            process=Process.hierarchical,
            verbose=True,


            manager_llm=LLM(model="openai/gpt-4o-mini"),


            chat_llm=LLM(model="openai/gpt-4o-mini"),
        )


