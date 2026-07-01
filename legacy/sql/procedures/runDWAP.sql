-- SqlProcedure: [dbo].[runDWAP]

set nocount on

--clear the cache
exec clearCache

--get all stocks, then run dwapio only if the last stock value 
--was $10 or more
declare @stockID int, @lastval money
declare @included int
declare allstock cursor for
		select stockid from stock where lastprice > 10 and lastvolume > 100000 order by stockid asc
open allstock
fetch next from allstock into @stockID
	while @@fetch_status=0
		begin		
			/*
			select @included = count(*) from stockinteresting where stockID = @stockid
			if @included = 0
				begin
					select @included = count(*) from holdingpen where stockID = @stockID
				end
		
			--if we don't have DWAP info on the stock, let's get it
			if @included = 0
				begin
					select @included = count(*) from datacache where stockID=@stockID
				end
			*/
			--only do DWAP on stocks we haven't triggered yet
			--if @included = 0
			--	begin
					exec DWAPIO @StockID, @StartDate, @EndDate
			--	end
			--exec runWatches @StockID, @StartDate //do we really need this here?
		fetch next from allstock into @stockID
		end
close allstock
deallocate allstock


set nocount off
