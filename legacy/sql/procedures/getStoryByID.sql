-- SqlProcedure: [dbo].[getStoryByID]

set nocount on

	select * from story where storyID=@storyID

set nocount off
