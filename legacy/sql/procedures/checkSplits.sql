-- SqlProcedure: [dbo].[checkSplits]

set nocount on

	if exists (select * from stocksplit where atwhen = @atwhen and ApplyDate is null)
		begin
			--now apply the splits
			declare @sid int
			declare spcur cursor for
				select stockID from stocksplit where applydate is null and atwhen=@atwhen
		
			open spcur
				fetch next from spcur into @sid
					while @@fetch_status=0
						begin
						exec applysplit @sid, @atwhen
						fetch next from spcur into @sid
						end
			close spcur
			deallocate spcur
		end

set nocount off
