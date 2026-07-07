-- SqlProcedure: [dbo].[saveStory]

set nocount on

	if @storyID is null
		begin
			--create a new story
			insert into Story (AtWhen, Title, Story, Status)
				select @AtWhen, @Title, @Story, @Status

			select @@IDENTITY
		end
	else
		begin
			--update existing
			if @atwhen is null
				begin
					update story
					set Title = @Title,
					Story = @Story,
					Status=@status
					where storyID=@StoryID
				end
			else
				begin
					update story
					set AtWhen = @AtWhen,
					Title = @Title,
					Story = @Story,
					Status=@status
					where storyID=@StoryID
				end
			select @StoryID
		end

set nocount off
