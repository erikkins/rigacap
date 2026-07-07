-- SqlProcedure: [dbo].[LastPriceFix]
-- header:
-- CREATE proc [dbo].[LastPriceFix]

CREATE proc [dbo].[LastPriceFix]
as
set nocount on

	declare @sid int, @ldd datetime, @lp money
	declare @maxdate datetime, @maxprice money, @maxvol bigint

	declare pricefix cursor for
		select stockID, lastdatadate from stock

	open pricefix
		fetch next from pricefix into @sid, @ldd
		while @@fetch_status=0
			begin
				select @maxdate = max(atwhen)
				from stockData 
				where stockID=@sid			

				if @maxdate > @ldd
					begin
						Print 'Fixing ' + convert(varchar,@sid)
						select @maxprice=price, @maxvol = volume
						from stockdata
						where stockID=@sid
						and atwhen = @maxdate

						update stock
						set lastprice = @maxPrice,
						lastVolume = @maxVol,
						lastDataDate = @ldd
						where stockID=@sid				

					end
			
			fetch next from pricefix into @sid, @ldd	
			end

	close pricefix
	deallocate pricefix

set nocount off
