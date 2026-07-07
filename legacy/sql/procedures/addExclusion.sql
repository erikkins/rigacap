-- SqlProcedure: [dbo].[addExclusion]

set nocount on

	if not exists (select * from ExclusionList where ticker=@Ticker)
		begin
			insert into ExclusionList (Ticker, Exchange)
				Values(@Ticker, @Exchange)
		end

set nocount off
