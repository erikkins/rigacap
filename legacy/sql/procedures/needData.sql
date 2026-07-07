-- SqlProcedure: [dbo].[needData]

set nocount on

	--if there's no data on the @atwhen for this stock (e.g. others have it)
	--then return 1, else 0...also take into consideration holidays
	declare @price money
	select @price = Price 
	from StockData 
	where stockID=@stockID and atwhen = @atwhen

	if @price is not null
		begin
			return 0
		end

	--we've gotten this far, go get the data
	if dbo.fnIsHoliday(@atwhen)=1
		begin
			return 0
		end
	else
		begin

			declare @others int
			select @others = count(*) from stockdata where atwhen = @atwhen
			if @others > 0
				begin
					return 1
				end
			else
				begin
					return 0
				end
		end

set nocount off
