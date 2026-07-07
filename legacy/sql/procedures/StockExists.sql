-- SqlProcedure: [dbo].[StockExists]

set nocount on

	declare @ret bit
	set @ret = 0

	if exists (select * from Stock where ticker=@ticker)
		begin
			set @ret = 1
		end

	if @ret = 0
		Begin
			if exists (select * from ExclusionList where ticker=@ticker)
				begin
					set @ret = 1
				end
		End

	select @ret
set nocount off
