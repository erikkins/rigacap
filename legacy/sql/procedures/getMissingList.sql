-- SqlProcedure: [dbo].[getMissingList]

set nocount on

if @atwhen < '1/1/2006'
	begin
		return 
	end

	if dbo.fn_IsWeekDay(@atwhen)=1 and dbo.fnIsHoliday(@atwhen)=0
		begin

	--declare @total int
	--select @total = count(*) from stockdata where atwhen =@atwhen

	--if @total > 0
		--begin
			--select s.stockID, ticker
			--from Stock s
			--inner join StockData sd on sd.stockID = s.stockID
			--where s.stockID not in (select stockID from stockdata where atwhen=@atwhen)
			--and Active=1			
			--group by s.stockID, ticker
			--having max(sd.atwhen) > dateadd(day,-10,@atwhen)
		--end
		select s.stockID, ticker
		from Stock s
		inner join StockData sd on sd.StockID=s.StockID
		where s.stockID not in (select stockID from stockData where atwhen=@atwhen)
		and s.stockID not in (select msd.stockID from MissedStockData msd where msd.stockID=s.stockID and msd.atwhen=@atwhen)
		and s.Active=1 
		group by s.StockID, ticker

		end
set nocount off
