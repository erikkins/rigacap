-- SqlProcedure: [dbo].[getNext10Stories]

set nocount on

	declare @tdates table
	(
		atwhen datetime
	)

	insert @tdates
		select @atwhen

	declare @cnt int
	select @cnt = 1
	while @cnt <= 14
		begin
			if dbo.fn_IsWeekDay(DateAdd(day,@cnt,@atwhen)) = 1 
				begin					
					insert into @tdates
						select DateAdd(day,@cnt,@atwhen)
				end
		select @cnt = @cnt + 1
		end

	select td.atwhen, storyID,title,story,status from @tdates td
	left join story s on s.atwhen=td.atwhen

set nocount off
