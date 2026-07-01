-- SqlProcedure: [dbo].[getStory]

set nocount on

	select * from story where atwhen =@atwhen

set nocount off
